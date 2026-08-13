"""
UTIM Production Server — FastAPI Application
Deployed at: api.utim.dev

Environment variables (set in Railway dashboard):
  DATABASE_URL         PostgreSQL connection string (auto-set by Railway Postgres plugin)
  OPENROUTER_API_KEY   OpenRouter API key for LLM calls
  UTIM_MASTER_KEY      Secret key for admin endpoints (/auth/topup)
  LOG_LEVEL            (optional) DEBUG | INFO | WARNING  (default: INFO)
"""
from __future__ import annotations

import logging
import os
from typing import List, Dict, Any

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text
from pydantic import BaseModel
from openai import AsyncOpenAI

from .db import init_db, SessionLocal
from .logging_config import configure_logging, RequestLoggingMiddleware
from .rate_limit import limiter
from .cli_auth import cli_signature_middleware
from .attribution import attach_openrouter_headers
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .routes import auth_router, credit_router, session_router, completion_router, quota_router, share_router, feedback_router, referral_router, quota_share_router, marketplace_router, rewards_router

from .routes.security_routes import router as security_router
from .models import list_models
from .auth import get_admin_user


# ── Logging ───────────────────────────────────────────────────────────────────

configure_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("utim.server")

# ── Database init ─────────────────────────────────────────────────────────────

init_db()

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="UTIM Agent Server",
    description=(
        "Production backend for the UTIM CLI agent. "
        "Handles authentication, credit billing, LLM proxying, and chat history."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.on_event("startup")
def start_model_registry_agent():
    from .model_agent import model_agent
    model_agent.start()
    
    # Local LLM server disabled — all background tasks route to fast remote models.
    pass

@app.on_event("shutdown")
def stop_model_registry_agent():
    from .model_agent import model_agent
    model_agent.stop()

# CORS — explicit allowlist ONLY. No regex wildcards on *.utim.dev because
# a wildcard DNS record compromise (or a misissued wildcard cert) would let
# any attacker subdomain (e.g. evil.utim.dev) make authenticated cross-origin
# requests with the user's cookies. Keep this list short and explicit.
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS")
if allowed_origins_env:
    allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    allowed_origins = [
        "https://utim.dev",
        "https://www.utim.dev",
        "https://api.utim.dev",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ]

# Deduplicate while preserving order
_seen = set()
allowed_origins = [o for o in allowed_origins if not (o in _seen or _seen.add(o))]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    # No allow_origin_regex. Localhost matches are already in the explicit
    # list above. Subdomain wildcards (e.g. *.utim.dev) are explicitly
    # disallowed to prevent DNS-takeover / wildcard-cert-issuance attacks.
    allow_origin_regex=None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os as _os

_DEFAULT_MAX = int(_os.environ.get("UTIM_MAX_CONTENT_LENGTH", str(4_000_000)))       # 4 MB
_LARGE_MAX   = int(_os.environ.get("UTIM_MAX_CONTENT_LENGTH_LARGE", str(5_368_709_120)))  # 5 GB

# Routes that need a higher body cap than the default 4 MB
_LARGE_UPLOAD_PREFIXES = (
    "/marketplace/publish",
    "/marketplace/security-check",
    "/shares/upload",          # workspace share packages — up to 5 GB (Ultimate plan)
)


def _effective_max_for_path(path: str) -> int:
    if any(path.startswith(p) for p in _LARGE_UPLOAD_PREFIXES):
        return _LARGE_MAX
    return _DEFAULT_MAX


class LimitUploadSize(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds the per-route cap.

    Uses a single check against `_effective_max_for_path` so that routes
    listed in `_LARGE_UPLOAD_PREFIXES` (e.g. /shares/upload) are allowed
    up to 5 GB without being double-checked against the 4 MB default.
    """

    async def dispatch(self, request, call_next):
        cl = request.headers.get("content-length")
        if cl:
            try:
                cap = _effective_max_for_path(request.url.path)
                if int(cl) > cap:
                    return JSONResponse(
                        {"detail": f"Request body too large (limit {cap // (1024 * 1024)} MB for this route)"},
                        status_code=413,
                    )
            except ValueError:
                pass
        return await call_next(request)


app.add_middleware(LimitUploadSize)

# CLI signature verification — rejects requests that don't carry a valid
# X-UTIM-CLI-Signature for protected routes when UTIM_REQUIRE_CLI_SIGNATURE=1.
app.add_middleware(BaseHTTPMiddleware, dispatch=cli_signature_middleware)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(auth_router)
app.include_router(credit_router)
app.include_router(session_router)
app.include_router(completion_router)
app.include_router(quota_router)
app.include_router(share_router)
app.include_router(feedback_router)
app.include_router(referral_router)
app.include_router(quota_share_router)
app.include_router(marketplace_router, prefix="/marketplace")
app.include_router(security_router)
app.include_router(rewards_router)




# ── Support Chatbot Endpoint ──────────────────────────────────────────────────

class SupportChatRequest(BaseModel):
    model: str = "openrouter/free"
    messages: List[Dict[str, Any]]
    tools: List[Dict[str, Any]] | None = None

@app.post("/api/support-chat", tags=["support"])
async def support_chat(req: SupportChatRequest):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return {
            "reply": "Support API key not configured on the server. Please set OPENROUTER_API_KEY.",
            "message": {"role": "assistant", "content": "Support API key not configured on the server."}
        }
    
    try:
        # Build an httpx AsyncClient pre-loaded with the canonical OpenRouter
        # attribution headers (HTTP-Referer, X-Title, User-Agent). OpenRouter
        # shows "UTIM CLI Agent" in its logs ONLY when these are present on
        # every outbound call — previously the AsyncOpenAI default headers
        # were empty, so the app showed up as "unknown" in OpenRouter analytics.
        try:
            import httpx
            from .attribution import OPENROUTER_HEADERS
            http_client = httpx.AsyncClient(headers=OPENROUTER_HEADERS, timeout=30)
        except Exception:
            http_client = None  # fall back to defaults if httpx not available

        client_kwargs = {"api_key": key, "base_url": "https://openrouter.ai/api/v1"}
        if http_client is not None:
            client_kwargs["http_client"] = http_client
        client = AsyncOpenAI(**client_kwargs)

        kwargs = {
            "model": req.model,
            "messages": req.messages,
            "timeout": 30,
        }
        if req.tools:
            kwargs["tools"] = req.tools

        response = await client.chat.completions.create(**kwargs)
        choice_message = response.choices[0].message
        
        tool_calls = None
        if choice_message.tool_calls:
            tool_calls = []
            for t in choice_message.tool_calls:
                tool_calls.append({
                    "id": t.id,
                    "type": t.type,
                    "function": {
                        "name": t.function.name,
                        "arguments": t.function.arguments
                    }
                })

        return {
            "reply": choice_message.content or "",
            "message": {
                "role": "assistant",
                "content": choice_message.content or "",
                "tool_calls": tool_calls
            }
        }
    except Exception as exc:
        logger.error(f"support_chat_error: {exc}")
        return {
            "reply": f"Sorry, I had trouble processing that request: {str(exc)}",
            "message": {
                "role": "assistant",
                "content": f"Sorry, I had trouble processing that request: {str(exc)}"
            }
        }

# ── Core endpoints ────────────────────────────────────────────────────────────

def _find_changelog_path():
    import os
    # Search multiple candidates for CHANGELOG.md (robust on both local dev and Railway production)
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "CHANGELOG.md"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "CHANGELOG.md"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "CHANGELOG.md"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "CHANGELOG.md"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


@app.get("/health", tags=["system"], summary="Health check")
def health():
    """Always returns 200 so Railway health checks pass.
    DB status is reported in the body for diagnostics.
    """
    db_status = "ok"
    db_error = None
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as exc:
        db_error = str(exc)
        logger.error(f"health_db_error: {exc}")
        db_status = "error"

    # Derive version dynamically from CHANGELOG.md so a deploy auto-updates it
    try:
        import re as _re
        _cl_path = _find_changelog_path()
        _version = "1.47.16"
        if _cl_path:
            with open(_cl_path, "r", encoding="utf-8") as _f:
                for _line in _f:
                    _m = _re.match(r"^##\s+\[?([0-9a-zA-Z\.\-]+)\]?\s*-", _line.strip())
                    if _m:
                        _version = _m.group(1)
                        break
    except Exception:
        _version = "1.47.16"

    # Always return 200 — Railway must see 200 or it will keep restarting.
    # DB connectivity errors are surfaced in the body for debugging.
    body = {"status": "ok" if db_status == "ok" else "degraded", "db": db_status, "version": _version}
    if db_error:
        body["db_error"] = db_error
    return JSONResponse(content=body, status_code=200)


@app.get("/models", tags=["system"], summary="List available LLM models from ModelDB")
def models():
    from .db import SessionLocal, ModelDB
    db = SessionLocal()
    try:
        db_models = db.query(ModelDB).filter(ModelDB.is_active == True).all()
        if db_models:
            return [
                {
                    "model_id": m.model_id,
                    "name": m.name,
                    "provider": m.provider,
                    "context_window": m.context_window,
                    "max_output_tokens": m.max_output_tokens,
                    "is_free": m.is_free,
                    "is_vision": m.is_vision,
                    "is_reasoning": m.is_reasoning,
                    "tags": m.tags or [],
                    "capabilities": m.capabilities or [],
                }
                for m in db_models
            ]
    except Exception:
        pass
    finally:
        db.close()

    return [
        {
            "model_id": m.model_id,
            "provider": m.provider,
            "context_window": m.context_window,
            "max_output_tokens": m.max_output_tokens,
            "tags": m.tags,
            "capabilities": m.capabilities,
            "is_free": "free" in (m.tags or []) or m.model_id.endswith(":free"),
            "is_vision": m.vision,
            "is_reasoning": "reasoning" in (m.capabilities or []),
            "description": m.description,
        }
        for m in list_models()
    ]


@app.get("/models/catalog", tags=["system"], summary="Structured model catalog grouped by tool capability")
def models_catalog():
    """Return a structured model catalog organised by tool/subagent use-case.

    The catalog only includes models from the 12 premium providers:
    Claude, Google, xAI, DeepSeek, Qwen, MoonshotAI, MiniMax, KwaiPilot,
    OpenAI, Z.ai, StepFun, Xiaomi.

    Response shape:
    {
        "main_agent":    [...],  // text->text models for main agent
        "plan_project":  [...],  // text->text models for plan_project tool
        "analyze_image": [...],  // vision (image->text) models
        "image_gen":     [...],  // image output models
        "all_text":      [...],  // all registered text->text models (including free)
    }
    """
    from .models import get_model_catalog
    return get_model_catalog()



@app.get("/status", tags=["system"], summary="Aggregate usage stats (admin)")
def status(_: None = Depends(get_admin_user)):
    """Global token usage and session counts."""
    from sqlalchemy import func
    from .db import Conversation, Transaction
    db = SessionLocal()
    try:
        total_in = db.query(func.sum(Conversation.token_usage_input)).scalar() or 0
        total_out = db.query(func.sum(Conversation.token_usage_output)).scalar() or 0
        sessions = db.query(Conversation).count()
        total_deducted = (
            db.query(func.sum(Transaction.amount))
            .filter(Transaction.kind == "deduction")
            .scalar() or 0
        )
    finally:
        db.close()

    return {
        "sessions": sessions,
        "total_input_tokens": int(total_in),
        "total_output_tokens": int(total_out),
        "total_credits_deducted": abs(float(total_deducted)),
    }


@app.get("/api/releases", tags=["system"], summary="Get parsed CHANGELOG.md")
def get_changelog():
    import os
    import re
    import datetime
    
    changelog_path = _find_changelog_path()
    if not changelog_path:
        return []

    try:
        with open(changelog_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Failed to read changelog file: {e}")
        return []

    versions = []
    current_version = None
    current_group = None

    type_map = {
        "added": "feature",
        "changed": "update",
        "fixed": "fix",
        "security": "security"
    }

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
            
        ver_match = re.match(r"^##\s+\[?([0-9a-zA-Z\.\-]+)\]?\s*-\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", line)
        if ver_match:
            version_str = ver_match.group(1)
            date_str = ver_match.group(2)
            try:
                dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                date_str = dt.strftime("%B %d, %Y")
            except Exception:
                pass
                
            current_version = {
                "version": version_str,
                "date": date_str,
                "changes": []
            }
            versions.append(current_version)
            current_group = None
            continue

        group_match = re.match(r"^###\s+(.+)$", line)
        if group_match and current_version is not None:
            group_name = group_match.group(1).lower().strip()
            group_type = type_map.get(group_name, "update")
            
            current_group = {
                "type": group_type,
                "items": []
            }
            current_version["changes"].append(current_group)
            continue

        item_match = re.match(r"^[\-\*]\s+(.+)$", line)
        if item_match and current_version is not None:
            if current_group is None:
                current_group = {
                    "type": "update",
                    "items": []
                }
                current_version["changes"].append(current_group)
            item_text = item_match.group(1)
            item_text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", item_text)
            current_group["items"].append(item_text)

    return versions


# ── Global error handler ──────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        extra={"path": request.url.path, "error": str(exc)},
        exc_info=True,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
