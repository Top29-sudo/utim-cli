"""
UTIM Production Server — Firebase token verification (no service account needed)

How it works:
  Firebase ID tokens are standard RS256-signed JWTs. The public keys are
  published by Google at a well-known URL. We download them (cached for 1h)
  and verify the token signature ourselves — completely serverless, no
  service account JSON required.

  This is the same approach used by every Firebase REST client library.
  See: https://firebase.google.com/docs/auth/admin/verify-id-tokens#verify_id_tokens_using_a_third-party_jwt_library

Railway env vars needed:  NONE — only the public Firebase project config is used.

Firebase project:  u-t-i-m-39c26
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger("utim.firebase")

# ── Firebase project (public config — safe to embed) ──────────────────────────
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "u-t-i-m-39c26")

# Google's public key endpoint for Firebase tokens
_CERT_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)

# ── Public key cache (refreshed when Cache-Control max-age expires) ───────────
_cert_cache: dict = {}          # {kid: public_key_pem}
_cert_cache_until: float = 0.0  # unix timestamp


def _get_public_keys() -> dict[str, str]:
    """Return Firebase's current public signing keys, caching per max-age."""
    global _cert_cache, _cert_cache_until

    if time.time() < _cert_cache_until and _cert_cache:
        return _cert_cache

    try:
        resp = requests.get(_CERT_URL, timeout=10)
        resp.raise_for_status()

        # Parse Cache-Control: max-age=<seconds> to know when to refresh
        max_age = 3600  # default 1h
        cc = resp.headers.get("Cache-Control", "")
        for part in cc.split(","):
            part = part.strip()
            if part.startswith("max-age="):
                try:
                    max_age = int(part.split("=", 1)[1])
                except ValueError:
                    pass

        raw_certs = resp.json()
        parsed = {}
        try:
            from cryptography import x509
            for kid, cert_str in raw_certs.items():
                try:
                    cert = x509.load_pem_x509_certificate(cert_str.encode("utf-8"))
                    parsed[kid] = cert.public_key()
                except Exception:
                    parsed[kid] = cert_str
        except ImportError:
            parsed = raw_certs

        _cert_cache = parsed
        _cert_cache_until = time.time() + max_age
        logger.debug("firebase_keys_refreshed", extra={"key_count": len(_cert_cache)})
        return _cert_cache

    except Exception as exc:
        logger.error("firebase_key_fetch_error", extra={"error": str(exc)})
        if _cert_cache:
            return _cert_cache   # serve stale cache rather than failing hard
        raise ValueError(f"Could not fetch Firebase public keys: {exc}") from exc


# ── Token payload ─────────────────────────────────────────────────────────────

class FirebaseTokenPayload:
    def __init__(self, uid: str, email: str, name: str, email_verified: bool):
        self.uid = uid
        self.email = email
        self.name = name
        self.email_verified = email_verified


# ── Verification ──────────────────────────────────────────────────────────────

def verify_firebase_token(id_token: str) -> FirebaseTokenPayload:
    """
    Verify a Firebase ID token using Google's published public keys.

    No service account / firebase-admin SDK required.
    Raises ValueError with a human-readable message on failure.
    """
    try:
        import jwt as pyjwt   # PyJWT
    except ImportError:
        raise ValueError(
            "PyJWT is not installed. Add 'PyJWT[crypto]>=2.8.0' to requirements."
        )

    # 1. Decode header to find which key to use (kid)
    try:
        header = pyjwt.get_unverified_header(id_token)
    except pyjwt.exceptions.DecodeError as exc:
        raise ValueError(f"Malformed token header: {exc}") from exc

    kid = header.get("kid")
    alg = header.get("alg", "RS256")

    if alg != "RS256":
        raise ValueError(f"Unexpected algorithm '{alg}' — expected RS256.")

    # 2. Fetch matching public key & verify signature
    try:
        keys = _get_public_keys()
        if kid not in keys:
            raise ValueError(f"Public key for kid '{kid}' not found in Firebase certs.")
            
        public_key_pem = keys[kid]
        payload = pyjwt.decode(
            id_token,
            public_key_pem,
            algorithms=["RS256"],
            audience=FIREBASE_PROJECT_ID,
            options={"verify_exp": True},
            leeway=300,               # allow 300s clock skew
        )
    except Exception as exc:
        logger.error(f"strict_firebase_verification_error: {exc}")
        raise ValueError(f"Firebase token verification failed: {exc}") from exc

    uid = payload.get("user_id") or payload.get("sub") or ""
    if not uid:
        raise ValueError("Token missing 'user_id' / 'sub' claim.")

    email = payload.get("email", "")
    name  = payload.get("name", email.split("@")[0] if email else uid[:8])

    logger.info(
        "firebase_token_verified",
        extra={"uid": uid[:8] + "…", "email_domain": email.split("@")[-1] if email else ""},
    )

    return FirebaseTokenPayload(
        uid=uid,
        email=email,
        name=name,
        email_verified=payload.get("email_verified", False),
    )
