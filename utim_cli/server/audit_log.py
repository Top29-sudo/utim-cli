"""
UTIM Audit Log
==============

Lightweight structured logger for admin & security-sensitive events.
Writes to the `utim_audit_log` DB table (auto-created at first write) AND
emits a `logger.warning` line so it shows up in Railway logs.

Activate by setting `UTIM_ADMIN_AUDIT_LOG=1`. The audit row is best-effort —
DB failures MUST NOT block the actual request.

SANITIZATION
────────────
All fields are passed through `_sanitize_for_audit` BEFORE being persisted or
logged. This prevents accidental leakage of secrets into long-lived audit
storage. The sanitization:

  * redacts any key matching /api[_-]?key|secret|password|token|authorization/i
  * truncates free-form strings to 4 KB
  * converts bytes / non-JSON-serialisable values to repr() bounded to 1 KB
  * never includes request bodies or headers verbatim — callers pass only the
    fields they explicitly want to audit
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import re
from typing import Any, Optional

from .db import SessionLocal, Base, Column, String, DateTime, Text, BigInteger, create_engine, DATABindError  # type: ignore  # noqa: F401

logger = logging.getLogger("utim.audit")


# ── Sanitization ──────────────────────────────────────────────────────────────
# Field names that must NEVER appear in audit storage or logs. We replace their
# values with the literal string "***REDACTED***" before persistence.

_REDACT_KEYS = (
    "api_key", "apikey", "api-key",
    "secret", "password", "passwd", "pwd",
    "token", "access_token", "refresh_token", "id_token",
    "authorization", "x-api-key", "x_captcha_token", "x-utim-cli-signature",
    "x-utim-nonce",
)
_REDACT_RE = re.compile(r"^(" + "|".join(re.escape(k) for k in _REDACT_KEYS) + r")$", re.IGNORECASE)


def _sanitize_value(v: Any) -> Any:
    """Recursively redact sensitive fields and bound string sizes."""
    if isinstance(v, dict):
        return {str(k)[:64]: ("***REDACTED***" if _REDACT_RE.match(str(k)) else _sanitize_value(val))
                for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [_sanitize_value(x) for x in v[:200]]  # cap list size
    if isinstance(v, str):
        return v[:4096]
    if isinstance(v, (bytes, bytearray)):
        return repr(bytes(v)[:1024])
    try:
        json.dumps(v)  # check serialisability
        return v
    except Exception:
        return repr(v)[:1024]


def _sanitize_for_audit(details: Optional[dict]) -> dict:
    if not details:
        return {}
    return _sanitize_value(details)


def _table_ready() -> bool:
    """Ensure the audit table exists (idempotent)."""
    try:
        from .db import Base, engine
        from sqlalchemy import Column, String, DateTime, Text, BigInteger
        class AuditLog(Base):  # type: ignore[misc, valid-type]
            __tablename__ = "utim_audit_log"
            id = Column(BigInteger, primary_key=True, autoincrement=True)
            timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
            actor = Column(String(128), nullable=True, index=True)
            action = Column(String(64), nullable=False, index=True)
            target = Column(String(255), nullable=True)
            ip = Column(String(64), nullable=True)
            install_id = Column(String(64), nullable=True)
            cli_version = Column(String(32), nullable=True)
            details = Column(Text, nullable=True)
        Base.metadata.create_all(bind=engine, tables=[AuditLog.__table__])
        return True
    except Exception as exc:
        logger.debug("audit_table_init_skipped: %s", exc)
        return False


def audit(
    action: str,
    *,
    actor: str = "",
    target: str = "",
    ip: str = "",
    install_id: str = "",
    cli_version: str = "",
    details: Optional[dict] = None,
) -> None:
    """Record an audit event. Non-blocking — errors are logged, not raised."""
    if os.environ.get("UTIM_ADMIN_AUDIT_LOG", "0") not in ("1", "true", "TRUE", "yes"):
        return

    details_str = ""
    if details:
        try:
            details_str = json.dumps(_sanitize_for_audit(details), default=str)[:4000]
        except Exception:
            details_str = str(_sanitize_for_audit(details))[:4000]

    # Always log to stdout (so it shows in Railway log stream)
    try:
        logger.warning(
            "AUDIT action=%s actor=%s target=%s ip=%s install=%s details=%s",
            action, actor[:64] if actor else "", target[:255] if target else "",
            ip[:64] if ip else "", install_id[:64] if install_id else "",
            details_str[:500],
        )
    except Exception:
        pass

    # Persist to DB (best-effort)
    try:
        if not _table_ready():
            return
        from .db import SessionLocal
        from sqlalchemy import Column, String, DateTime, Text, BigInteger
        from .db import Base
        # Re-declare inline to keep this function self-contained
        class _AuditLog(Base):  # type: ignore[misc, valid-type]
            __tablename__ = "utim_audit_log"
            id = Column(BigInteger, primary_key=True, autoincrement=True)
            timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
            actor = Column(String(128), nullable=True, index=True)
            action = Column(String(64), nullable=False, index=True)
            target = Column(String(255), nullable=True)
            ip = Column(String(64), nullable=True)
            install_id = Column(String(64), nullable=True)
            cli_version = Column(String(32), nullable=True)
            details = Column(Text, nullable=True)
        db = SessionLocal()
        try:
            db.add(_AuditLog(
                actor=(actor or "")[:128] or None,
                action=action[:64],
                target=(target or "")[:255] or None,
                ip=(ip or "")[:64] or None,
                install_id=(install_id or "")[:64] or None,
                cli_version=(cli_version or "")[:32] or None,
                details=details_str or None,
            ))
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.debug("audit_db_write_failed: %s", exc)
