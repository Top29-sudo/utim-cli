"""
Referral System API routes.

Logic:
- Each user has a unique referral_code (8 hex chars stored on the User model).
- When a new user signs up with ?ref=<code>, the server stores the referrer's ID on their account.
- Every time a referred user's subscription payment is verified, the referrer earns a 2% discount
  on that exact plan (e.g. if B buys hobby, referrer gets 2% off hobby).
- Discounts stack per-plan up to 100%.  If the same referred user renews, the discount
  increments again.
- The discount is stored in a separate ReferralDiscount table so it's queryable per plan.
"""

import uuid
import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Session, relationship

from ..db import Base, get_db, SessionLocal
from ..auth import get_current_firebase_user
from ..db import User

logger = logging.getLogger("utim.referrals")

router = APIRouter()


# ── ORM Model ─────────────────────────────────────────────────────────────────

class ReferralDiscount(Base):
    """Tracks per-plan discount percentage earned by a referrer."""
    __tablename__ = "referral_discounts"
    __table_args__ = (
        UniqueConstraint("referrer_id", "plan_id", name="uq_referral_discount_referrer_plan"),
    )

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    referrer_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id    = Column(String(50), nullable=False)          # e.g. "hobby", "pro", "max"
    discount_pct = Column(Float, default=0.0, nullable=False) # 0-100
    referee_count = Column(Integer, default=0, nullable=False) # how many distinct referral purchases stacked this
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    referrer   = relationship("User", foreign_keys=[referrer_id], backref="referral_discounts")


# ── Pydantic Schemas ───────────────────────────────────────────────────────────

class RegisterReferralRequest(BaseModel):
    referral_code: str   # code of the referrer


# ── Helpers ────────────────────────────────────────────────────────────────────

MAX_DISCOUNT_PCT = 100.0
DISCOUNT_PER_REFERRAL = 2.0


def apply_referral_purchase(db: Session, referee_id: str, plan_id: str) -> bool:
    """
    Called after a successful payment by `referee_id`.
    Finds their referrer and increments the plan-specific discount by 2%.
    Returns True if a referrer was found and updated.
    """
    referee = db.query(User).filter(User.id == referee_id).first()
    if not referee or not referee.referrer_id:
        return False

    referrer_id = referee.referrer_id

    # Normalise plan alias
    normalised = _normalise_plan(plan_id)

    discount_row = (
        db.query(ReferralDiscount)
        .filter(
            ReferralDiscount.referrer_id == referrer_id,
            ReferralDiscount.plan_id == normalised,
        )
        .first()
    )

    if not discount_row:
        discount_row = ReferralDiscount(
            referrer_id=referrer_id,
            plan_id=normalised,
            discount_pct=0.0,
            referee_count=0,
        )
        db.add(discount_row)

    new_pct = min(MAX_DISCOUNT_PCT, discount_row.discount_pct + DISCOUNT_PER_REFERRAL)
    discount_row.discount_pct = new_pct
    discount_row.referee_count += 1
    discount_row.updated_at = datetime.datetime.utcnow()

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"referral_discount_commit_error: {e}")
        return False

    logger.info(
        f"referral_discount_updated referrer={referrer_id} plan={normalised} "
        f"new_pct={new_pct} referee_count={discount_row.referee_count}"
    )
    return True


def _normalise_plan(plan_id: str) -> str:
    """Map frontend plan aliases to canonical DB plan ids."""
    mapping = {"starter": "pro", "professional": "max", "ultimate": "ultimate"}
    pid = plan_id.lower().strip()
    return mapping.get(pid, pid)


def get_referrer_discounts(db: Session, referrer_id: str) -> dict:
    """Return a dict of plan_id -> discount_pct for a given referrer."""
    rows = db.query(ReferralDiscount).filter(ReferralDiscount.referrer_id == referrer_id).all()
    return {r.plan_id: round(r.discount_pct, 2) for r in rows}


def consume_referral_discount(db: Session, referrer_id: str, plan_id: str) -> bool:
    """
    Resets the referrer's discount for the specified plan to 0.0
    after it has been applied to their subscription purchase/renewal.
    """
    normalised = _normalise_plan(plan_id)
    discount_row = (
        db.query(ReferralDiscount)
        .filter(
            ReferralDiscount.referrer_id == referrer_id,
            ReferralDiscount.plan_id == normalised,
        )
        .first()
    )
    if discount_row:
        discount_row.discount_pct = 0.0
        try:
            db.commit()
            logger.info(f"referral_discount_consumed referrer={referrer_id} plan={normalised}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"referral_discount_consume_error referrer={referrer_id} plan={normalised}: {e}")
    return False


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/api/referrals/register")
@router.post("/api/rewards/register")
def register_referral(
    req: RegisterReferralRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user),
):
    """
    Link the current user to a referrer by their referral_code.
    Can only be called once per user (if they don't already have a referrer).
    """
    if user.referrer_id:
        raise HTTPException(status_code=400, detail="You have already been linked to a referrer.")

    referrer = db.query(User).filter(User.referral_code == req.referral_code.strip()).first()
    if not referrer:
        raise HTTPException(status_code=404, detail="Referral code not found.")

    if referrer.id == user.id:
        raise HTTPException(status_code=400, detail="You cannot use your own referral code.")

    user.referrer_id = referrer.id
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to link referral: {e}")

    logger.info(f"referral_linked referee={user.id} referrer={referrer.id}")
    return {"success": True, "message": f"Successfully linked to referrer."}


@router.get("/api/referrals/info")
@router.get("/api/rewards/info")
def get_referral_info(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user),
):
    """
    Returns the current user's referral code, stats, and any discounts they have earned
    as a referrer.
    """
    # Ensure user has a referral code (backfill for old accounts)
    if not user.referral_code:
        user.referral_code = uuid.uuid4().hex[:8]
        try:
            db.commit()
        except Exception:
            db.rollback()

    # Count how many users they've referred
    try:
        referee_count = db.query(User).filter(User.referrer_id == user.id).count()
    except Exception:
        referee_count = 0

    # Get their earned discounts
    try:
        discounts = get_referrer_discounts(db, user.id)
    except Exception:
        discounts = {}

    # Did they sign up via a referral?
    referred_by = None
    if user.referrer_id:
        try:
            referrer = db.query(User).filter(User.id == user.referrer_id).first()
            if referrer:
                referred_by = {
                    "display_name": referrer.display_name or referrer.email.split("@")[0],
                    "email_hint": referrer.email[:3] + "***"
                }
        except Exception:
            pass

    return {
        "referral_code": user.referral_code,
        "referral_url": f"https://utim.dev/auth?ref={user.referral_code}",
        "referee_count": referee_count,
        "discounts": discounts,
        "referred_by": referred_by,
    }


@router.get("/api/referrals/leaderboard")
@router.get("/api/rewards/leaderboard")
def referral_leaderboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user),
):
    """
    Returns the top referrers by total referee count (anonymized).
    Also returns current user's rank.
    """
    from sqlalchemy import text
    try:
        result = db.execute(
            text("""
                SELECT u.id, u.display_name, COUNT(r.id) as cnt
                FROM users u
                LEFT JOIN users r ON r.referrer_id = u.id
                GROUP BY u.id, u.display_name
                HAVING COUNT(r.id) > 0
                ORDER BY cnt DESC
                LIMIT 10
            """)
        ).fetchall()

        board = []
        for i, row in enumerate(result):
            user_id = row[0]
            display_name = row[1]
            ref_count = row[2]

            discounts = db.query(ReferralDiscount).filter(ReferralDiscount.referrer_id == user_id).all()
            discount_str = ", ".join([f"{round(d.discount_pct)}% off {d.plan_id.capitalize()}" for d in discounts if d.discount_pct > 0])

            board.append({
                "rank": i + 1,
                "name": (display_name or "Anonymous")[:15],
                "referrals": ref_count,
                "discounts": discount_str,
                "is_me": user_id == user.id,
            })
    except Exception as e:
        logger.error(f"leaderboard_query_error: {e}")
        board = []

    return {"leaderboard": board}
