from __future__ import annotations
import json
import os
import uuid
from typing import List, Dict, Any, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from .db import Base, Conversation, User

# ── Local DB wiring ───────────────────────────────────────────────────────────
# Always use .utim/utim_local.db in the CURRENT WORKING DIRECTORY.
# This is the file bootstrap.py creates and backup.py backs up.
# We do NOT use the DATABASE_URL from server/db.py — that points at the
# production PostgreSQL server, which is unreachable from the local CLI.

_local_engine = None

def _get_local_engine():
    """Return a SQLAlchemy engine connected to ~/.utim/utim_local.db (global home)."""
    global _local_engine
    if _local_engine is None:
        from utim_cli.config import get_utim_dir
        utim_dir = get_utim_dir()
        utim_dir.mkdir(parents=True, exist_ok=True)
        db_path = utim_dir / "utim_local.db"
        url = f"sqlite:///{db_path}"
        _local_engine = create_engine(url, connect_args={"check_same_thread": False})
        # Ensure WAL mode for safe concurrent access from background threads
        @event.listens_for(_local_engine, "connect")
        def _set_wal(conn, _):
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
        # Create all tables if they don't exist yet (idempotent)
        Base.metadata.create_all(bind=_local_engine)
    return _local_engine

def close_history_db():
    """Close and dispose of the local SQLite database engine."""
    global _local_engine
    print(f"[DEBUG] close_history_db: _local_engine is {_local_engine}", flush=True)
    if _local_engine is not None:
        _local_engine.dispose()
        _local_engine = None



def _make_session():
    engine = _get_local_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()

# Default local user for fully local / unauthenticated operation
LOCAL_EMAIL = os.getenv("UTIM_EMAIL", "local@utim.dev")


def _parse_json_field(value, default=None):
    """Safely parse a DB field that may be a JSON string (SQLite Text) or already
    a Python object (PostgreSQL JSONB). Returns `default` on any failure."""
    if default is None:
        default = []
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value          # PostgreSQL JSONB already parsed
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return default
    return default


def _to_json(value):
    """Serialize a Python list/dict to a JSON string for SQLite Text storage.
    If the value is already a string, return it as-is."""
    if value is None:
        return "[]"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def get_or_create_user(db, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


class HistoryManager:
    def __init__(self):
        pass

    def get_session(self, session_id: str, email: str = None) -> Dict[str, Any] | None:
        db = _make_session()
        conv = db.query(Conversation).filter(Conversation.id == session_id).first()
        if not conv:
            db.close()
            return None
        res = {
            "session_id": conv.id,
            "model_id": conv.model_id,
            "messages": _parse_json_field(conv.messages),
            "turn_history": _parse_json_field(conv.turn_history),
            "redo_history": _parse_json_field(conv.redo_history),
            "usage": {
                "input_tokens": conv.token_usage_input,
                "output_tokens": conv.token_usage_output
            }
        }
        db.close()
        return res

    def create_session(self, model_id: str, email: str = None) -> str:
        email = email or LOCAL_EMAIL
        db = _make_session()
        user = get_or_create_user(db, email)
        session_id = str(uuid.uuid4())
        new_conv = Conversation(
            id=session_id,
            user_id=user.id,
            model_id=model_id,
            messages=_to_json([]),
            turn_history=_to_json([]),
            redo_history=_to_json([])
        )
        db.add(new_conv)
        db.commit()
        db.close()
        return session_id

    def add_messages(self, session_id: str, messages: List[Dict[str, Any]], email: str = None, first_user_msg: str = "", turn_history: List[Dict[str, Any]] = None, redo_history: List[Dict[str, Any]] = None):
        email = email or LOCAL_EMAIL
        db = _make_session()
        user = get_or_create_user(db, email)

        conv = db.query(Conversation).filter(Conversation.id == session_id).first()
        if conv:
            # Dynamically update user association when credentials change
            conv.user_id = user.id
            conv.messages = _to_json(messages)
            if turn_history is not None:
                conv.turn_history = _to_json(turn_history)
            if redo_history is not None:
                conv.redo_history = _to_json(redo_history)
                
            # Update title from first user message if we have one
            if first_user_msg and not conv.title:
                conv.title = (first_user_msg[:80] + "\u2026" if len(first_user_msg) > 80 else first_user_msg)
            
            db.commit()
        db.close()

    def checkpoint(self, session_id: str, messages: List[Dict[str, Any]], email: str = None, description: str = "auto"):
        pass

    def list_sessions(self, email: str = None):
        db = _make_session()
        conversations = db.query(Conversation).all()
        sessions = []
        for c in conversations:
            msgs = _parse_json_field(c.messages)
            has_user_msg = any(isinstance(m, dict) and m.get("role") == "user" for m in msgs)
            if not has_user_msg:
                continue
            first_user = next(
                (m.get("content", "") for m in msgs if isinstance(m, dict) and m.get("role") == "user"),
                ""
            )
            if isinstance(first_user, list):
                first_user = " ".join(p.get("text", "") for p in first_user if isinstance(p, dict))
            title = c.title or (first_user[:70] + "\u2026" if len(first_user) > 70 else first_user) or c.id[:12]
            sessions.append({
                "session_id": c.id,
                "model_id": c.model_id,
                "message_count": len(msgs),
                "title": title,
                "created_at": c.created_at.isoformat() if hasattr(c, "created_at") and c.created_at else "",
                "updated_at": c.updated_at.isoformat() if c.updated_at else "",
            })
        db.close()
        sessions.sort(key=lambda s: s["updated_at"], reverse=True)
        return sessions
