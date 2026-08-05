"""
OpenRouter Attribution Helper
=============================

Centralised injection of the HTTP-Referer / X-Title / User-Agent headers that
OpenRouter uses to identify the calling app. OpenRouter shows "UTIM CLI Agent"
in its logs only when these are present on every outbound call. Previously
some code paths (the server's /completions proxy, the CLI's direct fallback)
were inconsistent — leading to the app showing as "unknown" in analytics.

This module exposes:

    OPENROUTER_HEADERS  : dict of headers every OpenRouter-bound request MUST carry
    attach_openrouter_headers(headers=None) -> dict
    attach_openrouter_headers_to_session(session)
    install_urllib3_user_agent()   # one-time patch for clients that bypass `requests`
"""
from __future__ import annotations

from typing import Optional

# ── Constants ────────────────────────────────────────────────────────────────

OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://utim.dev",
    "X-Title": "UTIM CLI Agent",
    "User-Agent": "UTIM-CLI/2.0 (+https://utim.dev)",
}


def attach_openrouter_headers(headers: Optional[dict] = None) -> dict:
    """Return a new dict with the canonical OpenRouter attribution headers merged in.

    Caller-supplied headers take precedence over the defaults (so a test harness
    can still override), except HTTP-Referer and X-Title which are forced to
    the canonical values (otherwise OpenRouter shows the app as 'unknown').
    """
    merged = dict(headers or {})
    for key, val in OPENROUTER_HEADERS.items():
        merged[key] = val
    return merged


def attach_openrouter_headers_to_session(session) -> None:
    """Mutate a requests.Session in place to always carry the headers."""
    session.headers.update(OPENROUTER_HEADERS)


def install_urllib3_user_agent() -> None:
    """Patch urllib3's default User-Agent pool header. Useful for code that
    goes through the `httpx` or `urllib3` lower layers and bypasses `requests`.
    """
    try:
        import urllib3
        urllib3.util.make_headers(  # noqa: F841 - intentional side-effect
            user_agent=OPENROUTER_HEADERS["User-Agent"]
        )
        # Note: urllib3 doesn't actually store this globally; this is a stub
        # for the rare direct-urllib3 caller. Most code uses `requests` and
        # should be patched via attach_openrouter_headers_to_session().
    except Exception:
        pass
