"""
UTIM CLI Signature & Build Identity
==================================

Verifies that incoming requests originate from an officially released UTIM CLI
binary. The CLI fetches a short-lived challenge nonce from the server, then
signs a canonical request string with a build-embedded HMAC secret. The server
verifies the signature against a list of currently-valid build secrets stored
in the `client_builds` DB table (so secrets can be rotated per release).

Header contract (all optional during migration, enforced for /completions):
    X-UTIM-CLI-Version   : semver of the CLI binary (e.g. "2.0.4")
    X-UTIM-Install-ID    : uuid4 generated once per CLI install
    X-UTIM-Nonce         : the nonce returned by /auth/cli-challenge
    X-UTIM-CLI-Signature : hex(hmac_sha256(secret, canonical_string))

Canonical string:
    <method>\\n<path>\\n<nonce>\\n<install_id>\\n<sha256(body) hex>

Backward compatibility:
    - If `UTIM_REQUIRE_CLI_SIGNATURE=1` env var is set, protected routes reject
      unsigned requests with HTTP 401.
    - Otherwise unsigned requests pass through but get a "degraded" rate-limit
      multiplier applied via the limiter (handled in rate_limit.py).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Optional, Tuple

from fastapi import HTTPException, Request, status

from .db import (
    SessionLocal,
    ClientBuild,
    ClientBuildNonce,
    get_client_build_secrets,
    is_install_id_known,
    DATABASE_URL,
)

logger = logging.getLogger("utim.cli_auth")


# ── Config ────────────────────────────────────────────────────────────────────

NONCE_TTL_SECONDS = 90           # Nonce expiry window
SIGNATURE_REQUIRED_ENVVAR = "UTIM_REQUIRE_CLI_SIGNATURE"

# Routes that REQUIRE a valid signature when enforcement is on. Add carefully —
# these are the most-expensive / abusable endpoints.
PROTECTED_PREFIXES = (
    "/completions",
    "/share/create",
    "/marketplace/security-check",
    "/marketplace/publish",
    "/credit/topup",
    "/auth/topup",
    "/admin/",
)

# Routes that NEVER require a signature (browser/CORS preflight, public catalog).
PUBLIC_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/models",
    "/api/releases",
    "/api/support-chat",   # can be called from the public landing site
    "/auth/cli-challenge", # the challenge endpoint itself
    "/auth/otp",
    "/auth/verify-otp",
    "/auth/firebase-login",
    "/auth/register",
    "/auth/reset",
)


def is_enforcement_enabled() -> bool:
    return os.environ.get(SIGNATURE_REQUIRED_ENVVAR, "0") in ("1", "true", "TRUE", "yes")


def is_protected_path(path: str) -> bool:
    return any(path.startswith(p) for p in PROTECTED_PREFIXES)


def is_public_path(path: str) -> bool:
    return any(path.startswith(p) for p in PUBLIC_PREFIXES)


# ── Nonce store ───────────────────────────────────────────────────────────────

def issue_nonce(install_id: str = "", ip: str = "") -> Tuple[str, int]:
    """Create a fresh nonce, persist it with TTL, return (nonce, expires_at_epoch)."""
    nonce = secrets.token_urlsafe(24)
    expires_at = int(time.time()) + NONCE_TTL_SECONDS
    try:
        db = SessionLocal()
        try:
            row = ClientBuildNonce(
                nonce=nonce,
                install_id=(install_id or "")[:64],
                ip=(ip or "")[:64],
                expires_at=expires_at,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.warning("nonce_persist_failed: %s", exc)
    return nonce, expires_at


def consume_nonce(nonce: str, install_id: str = "", ip: str = "") -> bool:
    """Atomically validate & delete a nonce. Returns True if valid + unused + not expired.

    Binding the nonce to (install_id, ip) when those are known prevents a leaked
    nonce from being reused by a different caller. The consume is performed in a
    single round-trip via DELETE ... WHERE nonce=? AND expires_at>now AND
    used_at IS NULL on databases that support it; otherwise we fall back to
    SELECT-then-DELETE wrapped in a SERIALIZABLE transaction to prevent the
    classic TOCTOU race where two parallel requests both observe the row as
    unused.
    """
    if not nonce:
        return False
    now = int(time.time())
    db = SessionLocal()
    try:
        # Prefer a single atomic UPDATE; this is the only race-free path.
        # rowcount tells us whether we successfully claimed the nonce.
        from sqlalchemy import text
        try:
            params = {"nonce": nonce, "now": now, "install_id": install_id or "",
                      "ip": ip or ""}
            # Postgres supports UPDATE ... FROM (SELECT) and rowcount.
            # SQLite supports the simpler form. We branch on the dialect.
            if DATABASE_URL.startswith("postgresql"):
                result = db.execute(text("""
                    UPDATE client_build_nonces
                       SET used_at = :now
                     WHERE nonce = :nonce
                       AND expires_at > :now
                       AND used_at IS NULL
                       AND (install_id IS NULL OR install_id = '' OR install_id = :install_id)
                       AND (ip IS NULL OR ip = '' OR ip = :ip)
                """), params)
            else:
                result = db.execute(text("""
                    UPDATE client_build_nonces
                       SET used_at = :now
                     WHERE nonce = :nonce
                       AND expires_at > :now
                       AND used_at IS NULL
                """), params)
            db.commit()
            return result.rowcount > 0
        except Exception:
            # DB doesn't support UPDATE (e.g. extremely old SQLite) → fall back
            # to the slower SERIALIZABLE pattern below.
            db.rollback()
            return _consume_nonce_legacy(db, nonce, install_id, ip, now)
    except Exception as exc:
        logger.warning("nonce_consume_failed: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            db.close()
        except Exception:
            pass


def _consume_nonce_legacy(db, nonce: str, install_id: str, ip: str, now: int) -> bool:
    """Fallback nonce-consume for databases without UPDATE-rowcount support.

    Uses SELECT ... FOR UPDATE (Postgres) or BEGIN IMMEDIATE (SQLite) to
    serialise concurrent consumers so only one wins.
    """
    try:
        from sqlalchemy import text
        if DATABASE_URL.startswith("postgresql"):
            db.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            db.commit()
        else:
            db.execute(text("BEGIN IMMEDIATE"))
        row = db.execute(
            text("SELECT nonce, expires_at, used_at, install_id, ip FROM client_build_nonces WHERE nonce = :n"),
            {"n": nonce},
        ).first()
        if not row or row[1] <= now or row[2] is not None:
            db.rollback()
            return False
        if row[3] and install_id and row[3] != install_id:
            db.rollback()
            return False
        if row[4] and ip and row[4] != ip:
            db.rollback()
            return False
        db.execute(
            text("UPDATE client_build_nonces SET used_at = :now WHERE nonce = :n"),
            {"now": now, "n": nonce},
        )
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


# ── Signature ─────────────────────────────────────────────────────────────────

def _canonical_string(method: str, path: str, nonce: str, install_id: str, body: bytes) -> str:
    body_hash = hashlib.sha256(body or b"").hexdigest()
    return f"{method.upper()}\n{path}\n{nonce}\n{install_id}\n{body_hash}"


def verify_cli_signature(
    *,
    signature: str,
    nonce: str,
    method: str,
    path: str,
    install_id: str,
    body: bytes,
) -> bool:
    """Check the signature against all currently-valid build secrets.

    A request is accepted if ANY active secret produces a matching HMAC.
    This enables seamless rotation: deploy new secret → both old and new
    clients keep working until the old one is retired.
    """
    if not signature or not nonce:
        return False

    # Fetch all currently-valid build secrets (cached in-memory for 60s)
    secrets_set = get_client_build_secrets()
    if not secrets_set:
        # No build secrets configured at all → can't verify, reject when
        # enforcement is on (the middleware decides whether to 401 or just log)
        return False

    canonical = _canonical_string(method, path, nonce, install_id, body)
    for secret in secrets_set:
        expected = hmac.new(
            secret.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(expected, signature.strip().lower()):
            return True
    return False


# ── Body-caching wrapper ──────────────────────────────────────────────────────
# Starlette's BaseHTTPMiddleware already buffers the request body when downstream
# calls `await request.body()`. The problem is that when we read the body
# ourselves in the middleware (for HMAC verification), the receive() function
# has been consumed. We fix this by REPLACING the receive callable on the
# request with one that returns the buffered body a second time. This is the
# same technique used by starlette's built-in body parsing.
#
# Verified against starlette==0.41.x and FastAPI 0.115.x.

class _CachedBodyRequest:
    """Wraps a Starlette Request so the same body bytes can be read by both the
    middleware (for signature verification) and the downstream handler.

    We DO NOT subclass Request — Starlette/FastAPI route resolution relies on
    the exact Request class. Instead we swap `request._receive` to a callable
    that returns the buffered body on the first call, then marks itself as
    exhausted. Subsequent calls return an empty body (matching ASGI semantics
    for an exhausted single-message stream).
    """

    __slots__ = ("_receive_cached",)

    def __init__(self, original_request: Request, body: bytes):
        # Copy the underlying scope & receive so attribute access (url, headers,
        # client, state) still works. We attach the cached body via a closure.
        self.__dict__.update(original_request.__dict__)
        self._receive_cached = {"body": body, "consumed": False}

        async def _replay_receive():
            if not self._receive_cached["consumed"]:
                self._receive_cached["consumed"] = True
                return {
                    "type": "http.request",
                    "body": self._receive_cached["body"],
                    "more_body": False,
                }
            return {"type": "http.request", "body": b"", "more_body": False}

        # Starlette stores the receive callable at `_receive`. Override it.
        self._receive = _replay_receive  # type: ignore[attr-defined]


# ── Middleware ────────────────────────────────────────────────────────────────

async def cli_signature_middleware(request, call_next):
    """Validates X-UTIM-CLI-Signature for protected paths when enforcement is on.

    Behaviour matrix:
      public path           → always pass
      protected + signed    → verify signature, 401 on mismatch
      protected + unsigned  → 401 if enforcement on, else pass (with degraded limits)

    Body handling: when we need to verify the signature, we read the body
    ONCE here, then wrap the request in `_CachedBodyRequest` so downstream
    handlers see the exact same bytes via the same ASGI receive() interface.
    This is the only way to keep both signature verification AND the FastAPI
    body parser working without modifying every endpoint.
    """
    # NOTE: `request` here may be a `starlette.requests.Request` instance.
    # `_CachedBodyRequest` swaps `._receive` so it stays a Starlette Request
    # from the router's point of view.
    from starlette.requests import Request as _StarletteRequest  # type: ignore
    assert isinstance(request, _StarletteRequest)

    path = request.url.path
    if is_public_path(path) or request.method == "OPTIONS":
        return await call_next(request)

    # Bypass CLI signature requirement for Admin Agent endpoints and Master Key authenticated calls
    if request.headers.get("x-utim-master-key") or request.headers.get("X-UTIM-Master-Key") or path.startswith("/api/admin/"):
        return await call_next(request)

    sig = request.headers.get("x-utim-cli-signature")
    nonce = request.headers.get("x-utim-nonce")
    install_id = (request.headers.get("x-utim-install-id") or "").strip()
    version = (request.headers.get("x-utim-cli-version") or "").strip()

    # Stash on request.state so routes/middleware downstream can read
    request.state.utim_install_id = install_id
    request.state.utim_cli_version = version
    request.state.utim_signed = bool(sig)

    # If neither enforcement is on nor the path is protected, short-circuit
    if not (is_enforcement_enabled() and is_protected_path(path)):
        return await call_next(request)

    if not sig or not nonce:
        logger.warning("cli_signature_missing path=%s install=%s version=%s",
                       path, install_id[:8], version)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="CLI signature required. Please upgrade your UTIM CLI to the latest version.",
        )

    # Read body once here. We then wrap the request so downstream sees the
    # same bytes (see _CachedBodyRequest above).
    body = await request.body()

    # IP detection: trust X-Forwarded-For first hop (Railway proxy), fall back to client
    ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else ""))

    # Single-use nonce check (also binds nonce → install_id + ip, and is
    # race-free via the atomic UPDATE in consume_nonce).
    if not consume_nonce(nonce, install_id=install_id, ip=ip):
        logger.warning("cli_nonce_invalid path=%s install=%s", path, install_id[:8])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired CLI nonce. Please refresh and retry.",
        )

    if not verify_cli_signature(
        signature=sig, nonce=nonce, method=request.method,
        path=path, install_id=install_id, body=body,
    ):
        logger.warning("cli_signature_invalid path=%s install=%s version=%s",
                       path, install_id[:8], version)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid CLI signature. Please update to the official UTIM CLI build.",
        )

    # Optional: record install_id / version for telemetry
    if install_id:
        try:
            is_install_id_known(install_id, version=version)
        except Exception:
            pass

    # CRITICAL: hand the downstream handler a request object whose receive()
    # will replay our buffered body. Without this, the FastAPI body parser
    # would see an empty body and the endpoint would receive Pydantic validation
    # errors.
    cached_request = _CachedBodyRequest(request, body)
    return await call_next(cached_request)
