from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import datetime
import json

from ..db import get_db, Feedback, User
from ..auth import get_current_firebase_user, get_optional_firebase_user

router = APIRouter(prefix="/feedback", tags=["feedback"])

class FeedbackSubmitRequest(BaseModel):
    rating: int
    comment: Optional[str] = None
    chat_history: Optional[List[Dict[str, Any]]] = None

class FeedbackResponse(BaseModel):
    id: str
    user_email: str
    rating: int
    comment: Optional[str]
    chat_history: Optional[List[Dict[str, Any]]]
    created_at: datetime.datetime

@router.post("/submit")
def submit_feedback(
    req: FeedbackSubmitRequest,
    user: Optional[User] = Depends(get_optional_firebase_user),
    db: Session = Depends(get_db)
):
    if req.rating < 1 or req.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5.")
    
    chat_history_str = None
    if req.chat_history is not None:
        chat_history_str = json.dumps(req.chat_history)

    fb = Feedback(
        user_id=user.id if user else None,
        rating=req.rating,
        comment=req.comment,
        chat_history=chat_history_str
    )
    db.add(fb)
    db.commit()
    return {"status": "success", "message": "Feedback submitted successfully."}

@router.get("/list", response_model=List[FeedbackResponse])
def list_feedbacks(
    user: User = Depends(get_current_firebase_user),
    db: Session = Depends(get_db)
):
    ALLOWED_FIREBASE_IDS = {"JL763NoYOlRHV5WSkL9ySpz5gkI3", "HADaFqH9p0brRlMAs5mtEbwuBzk1"}
    if not user.firebase_uid or user.firebase_uid not in ALLOWED_FIREBASE_IDS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view feedbacks."
        )
    
    feedbacks = db.query(Feedback).order_by(Feedback.created_at.desc()).all()
    res = []
    for fb in feedbacks:
        parsed_chat_history = None
        if fb.chat_history:
            try:
                parsed_chat_history = json.loads(fb.chat_history)
            except Exception:
                pass
        res.append(FeedbackResponse(
            id=fb.id,
            user_email=fb.user.email if fb.user else "Anonymous User",
            rating=fb.rating,
            comment=fb.comment,
            chat_history=parsed_chat_history,
            created_at=fb.created_at
        ))
    return res
