"""
Extension Security Scanner & Auto-Fixer - UTIM Marketplace

POST /marketplace/security-check

Streams a structured, tool-assisted agentic security scan or fix session.
Model Suite (Primary with Fallbacks):
  1. openai/gpt-5.6-luna-pro (PRIMARY)
  2. minimax/minimax-m3
  3. qwen/qwen3.7-flash
  4. deepseek/deepseek-v4-flash-0731

Modes:
  - mode="check" (default): Model gets read_file, grep_search, web_search tools. edit_file IS NOT provided.
  - mode="fix": Model gets read_file, grep_search, web_search AND edit_file tools to auto-fix code.
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
from typing import Any, Generator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

from utim_cli.server.auth import get_current_user
from utim_cli.server.db import User

router = APIRouter(prefix="/marketplace", tags=["marketplace-security"])

# ── Models (Primary + Fallbacks) ───────────────────────────────────────────────

SCAN_MODELS = [
    "openai/gpt-5.6-luna-pro",
    "minimax/minimax-m3",
    "qwen/qwen3.7-flash",
    "deepseek/deepseek-v4-flash-0731",
]


# ── System Prompts ─────────────────────────────────────────────────────────────

_CHECK_SYSTEM_PROMPT = """You are UTIM Extension Security Agent — an expert cybersecurity AI tasked with reviewing user-submitted extensions for the UTIM CLI Marketplace.

Your job is to analyze submitted extension files for security risks before publication.

## Available Tools
- `read_file(path)`: Read content of any file in the extension
- `grep_search(query, path)`: Search across extension files for a pattern
- `web_search(query)`: Non-agentic web search to verify CVEs, package safety, or documentation

## Workflow
1. Review the list of extension files provided in the user prompt.
2. Call `read_file` to read and inspect key source files (manifests, Python code, markdown prompts, scripts).
3. Call `grep_search` to search for suspicious patterns across files (e.g. eval, exec, os.system, subprocess, socket, requests, urllib, ctypes, winreg, base64, pickle, marshal).
4. Call `web_search` if you need to check an unknown dependency, library, or security advisory.
5. Determine whether each file is CLEAN, WARNING, or THREAT.
6. Output JSON event objects for your analysis, one per line.

Output Format (JSON lines):
{"event": "thinking", "message": "..."}
{"event": "check", "file": "...", "pattern": "..."}
{"event": "finding", "file": "...", "verdict": "CLEAN|WARNING|THREAT", "detail": "..."}
{"event": "summary", "overall": "SAFE|NEEDS_FIXES|REJECTED", "issues": [...], "fixes_required": [...]}
"""

_FIX_SYSTEM_PROMPT = """You are UTIM Extension Security Auto-Fixer Agent.

Your job is to automatically fix all reported security vulnerabilities in the extension source code so that it passes security verification.

## Available Tools
- `edit_file(path, target_content, replacement_content)`: REPLACE exact text in a file to fix security issues
- `read_file(path)`: Read file content
- `grep_search(query, path)`: Search across extension files
- `web_search(query)`: Non-agentic web search for secure replacement patterns or documentation

## Instructions
1. Inspect the reported issues in the extension using `read_file` or `grep_search`.
2. For each issue, call `edit_file` to remove or safely refactor dangerous patterns (e.g. replacing dynamic `eval()` with safe parsing, sanitizing subprocess calls, or removing unauthorized network calls).
3. Confirm each edit is complete.
4. Output JSON event objects for your progress, one per line.
5. End with `{"event": "summary", "overall": "FIXED", "issues": [], "fixes_required": []}` when all fixes are applied.
"""


# ── Tool Definitions ───────────────────────────────────────────────────────────

_TOOLS_CHECK = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read content of a file in the extension.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file (e.g. agent.py)"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Search for a string or pattern across extension files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search string or pattern"},
                    "path": {"type": "string", "description": "Optional subpath to search in"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Non-agentic web search tool to check security advisories, CVEs, or documentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Web search query string"}
                },
                "required": ["query"],
            },
        },
    },
]

_TOOLS_FIX = _TOOLS_CHECK + [
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit/replace target content in a file within the extension.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file"},
                    "target_content": {"type": "string", "description": "Exact text substring to replace"},
                    "replacement_content": {"type": "string", "description": "New replacement text"},
                },
                "required": ["path", "target_content", "replacement_content"],
            },
        },
    }
]


# ── Web Search Helper ──────────────────────────────────────────────────────────

def _perform_web_search(query: str) -> str:
    """Non-agentic web search execution with sandboxed egress.

    Sandboxing rules (hard-coded; not configurable to prevent drift):
      * ONLY fetches from the DuckDuckGo HTML endpoint (no redirects followed)
      * Maximum response body size: 64 KB (read in chunks, abort if exceeded)
      * User-Agent is a fixed, non-spoofable string (no browser mimicry)
      * Upstream proxy may be injected via UTIM_WEB_SEARCH_PROXY env var
        (e.g. `socks5h://localhost:9050` to route through Tor) — this is the
        only knob operators need to flip to change egress policy globally.
      * Per-request timeout: 6 s
      * Results are sanitized: HTML stripped, snippets capped to 500 chars,
        max 4 snippets returned.
    """
    import requests
    # Validate query shape to prevent SSRF / injection via crafted q=
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        return "Refused: invalid query"
    # Strip control characters and anything that isn't typical search input
    safe_q = re.sub(r"[^\w\s\-\.\+\(\)\'\"]+", " ", query).strip()
    if not safe_q:
        return "Refused: query contained no valid characters"

    # Hard-coded allow-list. If you ever add a second engine, route through
    # the same allow-list check.
    ALLOWED_HOSTS = ("html.duckduckgo.com",)
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(safe_q)}"
        parsed = urllib.parse.urlparse(url)
        if parsed.hostname not in ALLOWED_HOSTS:
            logger.warning("web_search_blocked_host hostname=%s", parsed.hostname)
            return f"Refused: upstream host not in allow-list"
        headers = {"User-Agent": "UTIM-Scanner/2.0 (+https://utim.dev)"}
        proxy = os.environ.get("UTIM_WEB_SEARCH_PROXY", "").strip() or None
        proxies = {"https": proxy, "http": proxy} if proxy else None

        # Streamed fetch with size cap. requests doesn't expose a chunked
        # download hook, so we wrap with urllib3 PoolManager + read(16384).
        try:
            import urllib3
            http = urllib3.PoolManager(
                num_pools=2, maxsize=4, timeout=urllib3.Timeout(connect=3, read=6),
                retries=urllib3.Retry(total=1, backoff_factor=0.2),
            )
            r = http.request("GET", url, headers=headers, preload_content=False)
            try:
                chunks = []
                total = 0
                MAX = 64 * 1024
                for chunk in r.stream(8192):
                    total += len(chunk)
                    if total > MAX:
                        r.release_conn()
                        return "Web search response truncated (size cap exceeded)"
                    chunks.append(chunk)
                body = b"".join(chunks).decode("utf-8", errors="ignore")
            finally:
                try:
                    r.release_conn()
                except Exception:
                    pass
            if r.status != 200:
                return f"No web search results returned for query: '{safe_q}'"
            snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', body, re.DOTALL)
            clean_snippets = [
                re.sub(r'<[^>]+>', '', s).strip()[:500]
                for s in snippets[:4] if s.strip()
            ]
            if clean_snippets:
                return "\n---\n".join(clean_snippets)
        except Exception as exc:
            logger.warning("web_search_pool_failed: %s", exc)
            # Fallback to requests with timeout, still capped by urllib3
            r = requests.get(
                url, headers=headers, timeout=6, allow_redirects=False,
                proxies=proxies,
            )
            if r.status_code == 200 and len(r.content) <= 64 * 1024:
                snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', r.text, re.DOTALL)
                clean_snippets = [re.sub(r'<[^>]+>', '', s).strip()[:500] for s in snippets[:4] if s.strip()]
                if clean_snippets:
                    return "\n---\n".join(clean_snippets)
    except Exception as exc:
        logger.warning("web_search_failed: %s", exc)
    return f"No web search results returned for query: '{safe_q}'"


# ── Request Model ──────────────────────────────────────────────────────────────

class SecurityCheckRequest(BaseModel):
    extension_type: str                  # skill | miniagent | tool | mcp
    extension_name: str
    files: list[dict[str, str]]          # [{"name": "agent.py", "content": "..."}, ...]
    mode: str = "check"                  # "check" | "fix"
    issues: list[str] | None = None      # Issues from previous scan if mode == "fix"


# ── LLM Fallback Helper ────────────────────────────────────────────────────────

def _create_completion_with_fallback(client: OpenAI, messages: list[dict], tools: list[dict], scan_models: list[str] | None = None):
    models_to_try = scan_models if scan_models else SCAN_MODELS
    last_exc = None
    for model_id in models_to_try:
        try:
            res = client.chat.completions.create(
                model=model_id,
                messages=messages,
                tools=tools,
                temperature=0.1,
                max_tokens=4096,
            )
            return res, model_id
        except Exception as exc:
            last_exc = exc
            continue
    raise RuntimeError(f"All security scan models failed. Last error: {last_exc}")


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/security-check")
def security_check(
    req: SecurityCheckRequest,
    user: User = Depends(get_current_user),
):
    """Stream agentic security analysis or auto-fix session for an extension."""

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Security scanner not configured on server.")

    if not req.files:
        raise HTTPException(status_code=400, detail="No files provided for scanning.")

    # Isolated in-memory files dict for this request session
    files_dict: dict[str, str] = {f.get("name", "unknown"): f.get("content", "") for f in req.files}
    is_fix_mode = (req.mode == "fix")
    tools = _TOOLS_FIX if is_fix_mode else _TOOLS_CHECK
    system_prompt = _FIX_SYSTEM_PROMPT if is_fix_mode else _CHECK_SYSTEM_PROMPT

    file_list_lines = [f"- `{fname}` ({len(fcontent)} bytes)" for fname, fcontent in files_dict.items()]

    user_message = f"""
Extension Name: {req.extension_name}
Extension Type: {req.extension_type}
Mode: {req.mode.upper()}

Files in Extension:
{chr(10).join(file_list_lines)}

Please inspect the extension files using your tools (read_file, grep_search, web_search) and perform your security analysis.
"""
    if is_fix_mode and req.issues:
        user_message += f"\nReported Issues To Fix:\n" + "\n".join(f"- {i}" for i in req.issues)

    def _stream_session() -> Generator[str, None, None]:
        # Inject the canonical OpenRouter attribution headers via a custom
        # httpx client so OpenRouter shows the app as "UTIM CLI Agent" instead
        # of "unknown" in its analytics.
        try:
            import httpx
            from utim_cli.server.attribution import OPENROUTER_HEADERS
            http_client = httpx.Client(headers=OPENROUTER_HEADERS, timeout=60)
        except Exception:
            http_client = None

        client_kwargs = {"api_key": api_key, "base_url": "https://openrouter.ai/api/v1"}
        if http_client is not None:
            client_kwargs["http_client"] = http_client
        client = OpenAI(**client_kwargs)

        ext_type_clean = req.extension_type.lower().strip()

        # Rule 1: Skills or miniagents must have a proper README.md (>10 bytes)
        if ext_type_clean in ("skill", "miniagent"):
            has_readme = any(fname.lower() in ("readme.md", "readme.txt") and len(content.strip()) >= 10 for fname, content in files_dict.items())
            if not has_readme:
                msg = f"Missing README.md: Every {ext_type_clean} MUST include a proper README.md file."
                yield json.dumps({"event": "finding", "file": "README.md", "verdict": "THREAT", "detail": msg}) + "\n"
                yield json.dumps({"event": "summary", "overall": "REJECTED", "issues": [msg], "fixes_required": [msg]}) + "\n"
                return

        # Rule 2: Skill folder file restriction — ONLY SKILL.md and README.md allowed!
        if ext_type_clean == "skill":
            allowed_names = {"skill.md", "readme.md"}
            has_skill_md = False
            for fname in files_dict.keys():
                name_lower = fname.split("/")[-1].split("\\")[-1].lower()
                if name_lower not in allowed_names:
                    msg = f"Invalid Skill structure: Skills folder must ONLY contain SKILL.md and README.md. Found unexpected file: '{fname}'."
                    yield json.dumps({"event": "finding", "file": fname, "verdict": "THREAT", "detail": msg}) + "\n"
                    yield json.dumps({"event": "summary", "overall": "REJECTED", "issues": [msg], "fixes_required": [msg]}) + "\n"
                    return
                if name_lower == "skill.md":
                    has_skill_md = True
            if not has_skill_md:
                msg = "Invalid Skill structure: Skills folder must contain a 'SKILL.md' file."
                yield json.dumps({"event": "finding", "file": "SKILL.md", "verdict": "THREAT", "detail": msg}) + "\n"
                yield json.dumps({"event": "summary", "overall": "REJECTED", "issues": [msg], "fixes_required": [msg]}) + "\n"
                return

        accumulated_issues: list[str] = []
        accumulated_fixes: list[str] = []
        threats_found: list[str] = []
        warnings_found: list[str] = []
        summary_emitted: bool = False

        try:
            mode_desc = "Auto-Fixer" if is_fix_mode else "Scanner"
            yield json.dumps({"event": "started", "message": f"Security {mode_desc} started for '{req.extension_name}'"}) + "\n"

            messages: list[dict] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message.strip()},
            ]

            # Multi-turn tool loop (max 10 steps)
            for step in range(10):
                response, used_model = _create_completion_with_fallback(client, messages, tools)
                choice = response.choices[0]
                msg = choice.message

                # Send model info event if first step
                if step == 0:
                    yield json.dumps({"event": "thinking", "message": f"Using LLM Model: {used_model}"}) + "\n"

                # Check if model requested tool calls
                if msg.tool_calls:
                    messages.append(msg)
                    for tool_call in msg.tool_calls:
                        fn_name = tool_call.function.name
                        try:
                            fn_args = json.loads(tool_call.function.arguments)
                        except Exception:
                            fn_args = {}

                        tool_result = ""
                        if fn_name == "read_file":
                            p = fn_args.get("path", "")
                            content = files_dict.get(p, "File not found.")
                            tool_result = content[:6000]
                            yield json.dumps({"event": "check", "file": p, "pattern": f"Reading file content ({len(tool_result)} chars)"}) + "\n"

                        elif fn_name == "grep_search":
                            q = fn_args.get("query", "")
                            p = fn_args.get("path", "")
                            matches = []
                            for fname, fc in files_dict.items():
                                if not p or p in fname:
                                    for idx, line in enumerate(fc.splitlines()):
                                        if q.lower() in line.lower():
                                            matches.append(f"{fname}:{idx+1}: {line.strip()}")
                            tool_result = "\n".join(matches[:25]) if matches else "No matches found."
                            yield json.dumps({"event": "check", "file": p or "all", "pattern": f"Grep for '{q}' -> {len(matches)} matches"}) + "\n"

                        elif fn_name == "web_search":
                            q = fn_args.get("query", "")
                            yield json.dumps({"event": "thinking", "message": f"🔍 Web Search: '{q}'"}) + "\n"
                            tool_result = _perform_web_search(q)

                        elif fn_name == "edit_file" and is_fix_mode:
                            p = fn_args.get("path", "")
                            target = fn_args.get("target_content", "")
                            replacement = fn_args.get("replacement_content", "")

                            if p in files_dict and target in files_dict[p]:
                                files_dict[p] = files_dict[p].replace(target, replacement, 1)
                                tool_result = f"Successfully edited {p}."
                                yield json.dumps({
                                    "event": "file_edited",
                                    "file": p,
                                    "target": target,
                                    "replacement": replacement,
                                    "detail": f"Auto-fixed vulnerability in {p}"
                                }) + "\n"
                            else:
                                tool_result = f"Target content not found in {p}."

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result,
                        })

                else:
                    # Model produced text response
                    text_content = msg.content or ""
                    for line in text_content.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            if "event" in obj:
                                if obj.get("event") == "finding":
                                    v = obj.get("verdict", "")
                                    f = obj.get("file", "")
                                    d = obj.get("detail", "")
                                    if v in ("THREAT", "REJECTED"):
                                        threats_found.append(f"[{f}] {d}")
                                        accumulated_issues.append(f"[{f}] THREAT: {d}")
                                        accumulated_fixes.append(f"Remove dangerous vulnerability in {f}: {d}")
                                    elif v in ("WARNING", "NEEDS_FIXES"):
                                        warnings_found.append(f"[{f}] {d}")
                                        accumulated_issues.append(f"[{f}] WARNING: {d}")
                                        accumulated_fixes.append(f"Refactor suspicious pattern in {f}: {d}")

                                if obj.get("event") == "summary":
                                    summary_emitted = True

                                yield line + "\n"
                        except json.JSONDecodeError:
                            yield json.dumps({"event": "thinking", "message": line}) + "\n"
                    break

            # Fallback summary if LLM did not emit a explicit summary event
            if not summary_emitted:
                if threats_found:
                    overall = "REJECTED"
                elif warnings_found:
                    overall = "NEEDS_FIXES"
                elif is_fix_mode:
                    overall = "FIXED"
                else:
                    overall = "SAFE"

                if overall != "SAFE" and not accumulated_issues:
                    accumulated_issues.append(f"Security check completed with status: {overall}")
                    accumulated_fixes.append("Review code for unauthorized network calls, dynamic execution, or dangerous imports.")

                fallback_summary = {
                    "event": "summary",
                    "overall": overall,
                    "issues": accumulated_issues,
                    "fixes_required": accumulated_fixes,
                }
                yield json.dumps(fallback_summary) + "\n"

            yield json.dumps({"event": "done"}) + "\n"

        except Exception as exc:
            yield json.dumps({"event": "error", "message": str(exc)}) + "\n"

    return StreamingResponse(
        _stream_session(),
        media_type="application/x-ndjson",
    )
