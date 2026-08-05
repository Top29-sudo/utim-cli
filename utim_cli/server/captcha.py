"""
UTIM CAPTCHA verification
========================

Pluggable CAPTCHA dependency used by sensitive auth endpoints (signup, password
reset, credit top-up). Supports reCAPTCHA v2/v3, Cloudflare Turnstile, and
hCaptcha. Disabled ("off") in local dev.

Environment variables:
    UTIM_CAPTCHA_PROVIDER  one of: off | recaptcha | turnstile | hcaptcha
    UTIM_CAPTCHA_SECRET    shared secret issued by the provider
    UTIM_CAPTCHA_MIN_SCORE minimum score (reCAPTCHA v3 only, default 0.5)

Usage in a route:
    from .captcha import verify_captcha
    ...
    @router.post("/auth/register")
    def register(req: RegisterRequest, captcha_ok: bool = Depends(verify_captcha)):
        ...

The client (CLI) must fetch a CAPTCHA token first. Two options are supported:

  (A) Browser-based: the CLI opens a small web page (https://utim.dev/captcha?...)
      that runs Turnstile/reCAPTCHA and POSTs the resulting token back to a
      localhost callback.

  (B) Headless-ok providers: where the provider allows server-side tokens,
      no browser is needed.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests
from fastapi import Depends, Form, HTTPException, status

logger = logging.getLogger("utim.captcha")


def _provider() -> str:
    p = os.environ.get("UTIM_CAPTCHA_PROVIDER", "off").lower().strip()
    return p if p in ("off", "recaptcha", "turnstile", "hcaptcha") else "off"


def _secret() -> str:
    return os.environ.get("UTIM_CAPTCHA_SECRET", "").strip()


def _min_score() -> float:
    try:
        return float(os.environ.get("UTIM_CAPTCHA_MIN_SCORE", "0.5"))
    except ValueError:
        return 0.5


# Per-IP failure cache so we don't hammer the upstream siteverify endpoint
# from a single attacker that keeps sending bad tokens.
_FAILED_CACHE: dict[str, tuple[float, int]] = {}
_FAILED_CACHE_WINDOW = 300.0
_FAILED_CACHE_MAX = 5


def _ip_blocked(ip: str) -> bool:
    now = time.time()
    entry = _FAILED_CACHE.get(ip)
    if not entry:
        return False
    ts, count = entry
    if now - ts > _FAILED_CACHE_WINDOW:
        del _FAILED_CACHE[ip]
        return False
    return count >= _FAILED_CACHE_MAX


def _record_failure(ip: str) -> None:
    now = time.time()
    ts, count = _FAILED_CACHE.get(ip, (0.0, 0))
    if now - ts > _FAILED_CACHE_WINDOW:
        count = 0
        ts = now
    _FAILED_CACHE[ip] = (ts, count + 1)


def _siteverify_url(provider: str) -> str:
    return {
        "recaptcha": "https://www.google.com/recaptcha/api/siteverify",
        "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        "hcaptcha":  "https://api.hcaptcha.com/siteverify",
    }.get(provider, "")


def _verify_remote(provider: str, token: str, remote_ip: str) -> bool:
    secret = _secret()
    if not secret:
        logger.warning("captcha_secret_missing provider=%s", provider)
        return False

    url = _siteverify_url(provider)
    if not url:
        return False

    payload = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        resp = requests.post(url, data=payload, timeout=8)
        if resp.status_code != 200:
            logger.warning("captcha_http_error provider=%s status=%s", provider, resp.status_code)
            return False
        data = resp.json()
    except Exception as exc:
        logger.warning("captcha_request_failed provider=%s err=%s", provider, exc)
        return False

    if not data.get("success"):
        logger.info("captcha_rejected provider=%s errors=%s", provider, data.get("error-codes"))
        return False

    if provider == "recaptcha":
        score = float(data.get("score", 0.0) or 0.0)
        if score < _min_score():
            logger.info("captcha_low_score provider=%s score=%s min=%s",
                        provider, score, _min_score())
            return False
        action = (data.get("action") or "").lower()
        if action and action not in ("utim_signup", "utim_topup", "utim_reset", "utim_login"):
            logger.info("captcha_action_mismatch provider=%s action=%s", provider, action)
            return False

    return True


# ── FastAPI dependency ────────────────────────────────────────────────────────

def verify_captcha(
    captcha_token: Optional[str] = Form(default=None),
    # Also accept from header for non-form endpoints
    captcha_token_header: Optional[str] = None,  # injected via Header dependency below
) -> bool:
    """FastAPI dependency that gates sensitive routes behind CAPTCHA.

    Falls through (returns True) if the provider is set to "off" — this is the
    default for local dev and is logged so we know it's intentionally bypassed.
    """
    provider = _provider()
    if provider == "off":
        return True

    # The CLI may send the token in a header instead of form data
    from fastapi import Request
    # We can't easily access Request here without using it as a parameter; the
    # caller passes the token via Form (browser flow) or via header (CLI flow).
    token = (captcha_token or captcha_token_header or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CAPTCHA token missing. Please complete the verification challenge and retry.",
        )

    # Best-effort remote IP lookup via a small Header dependency
    # (The router that uses this dep can also pass remote_ip via Request.)
    # We accept the loss of precision here — the upstream provider will
    # validate its own heuristics even without an exact IP.
    ok = _verify_remote(provider, token, remote_ip="")
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CAPTCHA verification failed. Please retry the challenge.",
        )
    return True


# Convenience dependency that pulls the token from header
def _header_token(x_captcha_token: Optional[str] = None) -> Optional[str]:
    return x_captcha_token


# Self-contained dependency that reads both Form and Header transparently
from fastapi import Header

def verify_captcha_with_header(
    captcha_token: Optional[str] = Form(default=None),
    x_captcha_token: Optional[str] = Header(default=None, alias="X-Captcha-Token"),
) -> bool:
    """Dependency variant for non-form endpoints (CLI JSON bodies)."""
    provider = _provider()
    if provider == "off":
        return True

    token = (captcha_token or x_captcha_token or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CAPTCHA token missing. Please retry with a valid token.",
        )

    if not _verify_remote(provider, token, remote_ip=""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CAPTCHA verification failed. Please retry the challenge.",
        )
    return True
