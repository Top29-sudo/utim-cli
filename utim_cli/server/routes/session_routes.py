"""
Routes: /sessions — chat history CRUD
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import Conversation, get_db, User
from ..auth import get_current_user

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = logging.getLogger("utim.routes.sessions")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_json(val: Any) -> Any:
    if val is None:
        return []
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return []
    return val


def _dump_json(val: Any) -> str:
    return json.dumps(val, ensure_ascii=False)


def _conv_summary(c: Conversation) -> dict:
    msgs = _load_json(c.messages)
    first_user = next((m.get("content", "") for m in msgs if m.get("role") == "user"), "")
    if isinstance(first_user, list):
        first_user = " ".join(p.get("text", "") for p in first_user if isinstance(p, dict))
    title = c.title or (first_user[:70] + "…" if len(first_user) > 70 else first_user) or c.id[:12]
    return {
        "session_id": c.id,
        "model_id": c.model_id,
        "title": title,
        "message_count": len(msgs),
        "token_usage_input": c.token_usage_input,
        "token_usage_output": c.token_usage_output,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    model_id: str
    title: Optional[str] = None


class SaveMessagesRequest(BaseModel):
    messages: List[Dict[str, Any]]
    turn_history: Optional[List[Dict[str, Any]]] = None
    redo_history: Optional[List[Dict[str, Any]]] = None
    first_user_msg: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", status_code=201, summary="Create a new chat session")
def create_session(
    req: CreateSessionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sid = str(uuid.uuid4())
    conv = Conversation(
        id=sid,
        user_id=user.id,
        model_id=req.model_id,
        title=req.title,
        messages=_dump_json([]),
        turn_history=_dump_json([]),
        redo_history=_dump_json([]),
    )
    db.add(conv)
    db.commit()
    logger.info("session_created", extra={"session_id": sid, "user_id": user.id, "model": req.model_id})
    return {"session_id": sid}


@router.get("", summary="List all sessions (newest first)")
def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    total = db.query(Conversation).filter(Conversation.user_id == user.id).count()
    return {"total": total, "results": [_conv_summary(c) for c in q.all()]}


@router.get("/{session_id}", summary="Get a single session with full message history")
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = db.query(Conversation).filter(
        Conversation.id == session_id, Conversation.user_id == user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        **_conv_summary(conv),
        "messages": _load_json(conv.messages),
        "turn_history": _load_json(conv.turn_history),
        "redo_history": _load_json(conv.redo_history),
    }


@router.post("/{session_id}/messages", summary="Save / sync the full message array for a session")
def save_messages(
    session_id: str,
    req: SaveMessagesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = db.query(Conversation).filter(
        Conversation.id == session_id, Conversation.user_id == user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Session not found")

    conv.messages = _dump_json(req.messages)
    if req.turn_history is not None:
        conv.turn_history = _dump_json(req.turn_history)
    if req.redo_history is not None:
        conv.redo_history = _dump_json(req.redo_history)
    if req.first_user_msg and not conv.title:
        t = req.first_user_msg
        conv.title = (t[:80] + "…") if len(t) > 80 else t

    db.commit()
    logger.info("messages_saved", extra={
        "session_id": session_id,
        "user_id": user.id,
        "message_count": len(req.messages)
    })
    return {"status": "saved", "message_count": len(req.messages)}


@router.delete("/{session_id}", status_code=204, summary="Delete a session")
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = db.query(Conversation).filter(
        Conversation.id == session_id, Conversation.user_id == user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(conv)
    db.commit()
    logger.info("session_deleted", extra={"session_id": session_id, "user_id": user.id})
