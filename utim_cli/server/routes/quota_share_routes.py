"""
Quota Sharing API Routes
------------------------
Allows subscribed users to share regular (non-bonus) plan credits with users
they have directly referred.

How it works:
  1. Sender calls POST /api/quota-share/transfer → credits are deducted from sender,
     and a one-time RedeemCode is generated and returned.
  2. Sender gives that code to their referred user (or uses it themselves).
  3. Recipient calls POST /api/quota-share/redeem with the code → credits are added
     to their bonus_balance.

Rules:
  • Codes never expire.
  • Codes cannot be revoked once created.
  • Only directly referred users (or the sender themselves) can redeem a code.
  • Redeemed credits land in bonus_balance (Bonus Quota bar).
  • Bonus credits (credit.bonus_balance) on the sender side are never touched.

Endpoints:
  GET  /api/quota-share/info        — shareable balance, referred users list
  POST /api/quota-share/preview     — compute deduction breakdown (dry-run)
  POST /api/quota-share/transfer    — deduct from sender + generate redeem code
  POST /api/quota-share/redeem      — apply a redeem code to caller's bonus_balance
  GET  /api/quota-share/redeem/{code} — look up a code's details before redeeming
  GET  /api/quota-share/history     — list sent / received transfers for the caller

Deduction priority (sender side):
  1. Quota Bank  (credit.balance)
  2. Current Cycle remaining regular credits  (cycle_allowance - current_cycle_used)
  3. Unallocated plan credits (remaining future-cycle pool)
"""
from __future__ import annotations

import datetime
import logging
import secrets
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import (
    Credit, Plan, QuotaTransfer, RedeemCode, User, UserSubscription,
    get_db, get_max_bonus_limit,
)
from ..auth import get_current_firebase_user

router = APIRouter(tags=["quota-share"])
logger = logging.getLogger("utim.quota_share")

CYCLES_PER_MONTH = 144  # 30 days × 24 h / 5 h = 144 five-hour slots


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_active_sub(user: User, db: Session) -> Optional[UserSubscription]:
    return db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.status == "active",
    ).first()


def _get_plan(sub: UserSubscription, db: Session) -> Optional[Plan]:
    if not sub:
        return None
    return db.query(Plan).filter(Plan.id == sub.plan_id).first()


def _regular_plan_credits(plan: Plan) -> float:
    """Monthly regular shareable credits (excludes bonus pool)."""
    return float(plan.credits_per_month)


def _cycle_allowance(plan: Plan) -> float:
    return _regular_plan_credits(plan) / CYCLES_PER_MONTH


def _compute_remaining_cycles(sub: UserSubscription) -> int:
    now = datetime.datetime.utcnow()
    period_end = sub.current_period_end or (
        (sub.current_period_start or now) + datetime.timedelta(days=30)
    )
    seconds_left = max(0.0, (period_end - now).total_seconds())
    return max(1, int(seconds_left / (5 * 3600)))


def _compute_shareable_balance(sub: UserSubscription, plan: Plan, credit: Credit) -> dict:
    """
    Returns a breakdown of shareable credits across the three deduction sources.

    Sources (in deduction priority order):
      quota_bank        : credit.balance (rolled-over regular credits)
      current_cycle     : cycle_allowance - sub.current_cycle_used
      unallocated       : remaining future-cycle pool
    """
    cycle_allow = _cycle_allowance(plan)
    current_cycle_used = sub.current_cycle_used or 0.0
    current_cycle_balance = max(0.0, cycle_allow - current_cycle_used)
    quota_bank = max(0.0, credit.balance or 0.0)

    refills_processed = sub.refills_processed or 0
    allocated_to_cycles = refills_processed * cycle_allow
    unallocated_deducted = getattr(sub, "unallocated_deducted", 0.0) or 0.0
    unallocated = max(
        0.0,
        _regular_plan_credits(plan) - allocated_to_cycles - quota_bank - current_cycle_used - unallocated_deducted
    )

    remaining_cycles = _compute_remaining_cycles(sub)

    return {
        "quota_bank": quota_bank,
        "current_cycle_balance": current_cycle_balance,
        "unallocated": unallocated,
        "total_shareable": quota_bank + current_cycle_balance + unallocated,
        "remaining_cycles": remaining_cycles,
        "cycle_allowance": cycle_allow,
        "regular_plan_credits": _regular_plan_credits(plan),
    }


def _compute_deductions(amount: float, breakdown: dict) -> dict:
    """
    Calculate deduction breakdown for a requested amount.
    Priority: quota_bank → current_cycle → unallocated
    """
    remaining = amount
    from_bank = 0.0
    from_cycle = 0.0
    from_unallocated = 0.0

    take = min(remaining, breakdown["quota_bank"])
    from_bank = take
    remaining -= take

    if remaining > 0:
        take = min(remaining, breakdown["current_cycle_balance"])
        from_cycle = take
        remaining -= take

    if remaining > 0:
        take = min(remaining, breakdown["unallocated"])
        from_unallocated = take
        remaining -= take

    return {
        "from_bank": from_bank,
        "from_cycle": from_cycle,
        "from_unallocated": from_unallocated,
    }


def _future_cycle_quota(breakdown: dict, from_unallocated: float) -> Optional[float]:
    """Recalculate per-cycle credit allocation after draining from unallocated."""
    if from_unallocated <= 0:
        return None
    new_unallocated = max(0.0, breakdown["unallocated"] - from_unallocated)
    remaining_cycles = max(1, breakdown["remaining_cycles"])
    return new_unallocated / remaining_cycles


def _generate_redeem_code() -> str:
    """
    Generate a human-friendly redeem code.
    Format: UTIM-XXXX-XXXX-XXXX  (12 uppercase hex chars, grouped in 4s)
    """
    raw = secrets.token_hex(6).upper()  # 12 uppercase hex chars
    return f"UTIM-{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class QuotaSharePreviewRequest(BaseModel):
    recipient_uid: str = Field(..., description="Firebase UID of the referred recipient")
    amount: float = Field(..., gt=0, description="Credits to share (must be > 0)")


class QuotaShareTransferRequest(BaseModel):
    recipient_uid: str = Field(..., description="Firebase UID of the referred recipient")
    amount: float = Field(..., gt=0, description="Credits to transfer (must be > 0)")


class RedeemCodeRequest(BaseModel):
    code: str = Field(..., description="Redeem code (format: UTIM-XXXX-XXXX-XXXX)")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/api/quota-share/info")
def quota_share_info(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user),
):
    """
    Returns the caller's shareable credit breakdown and the list of referred
    users eligible to receive credits.
    """
    sub = _get_active_sub(user, db)
    if not sub:
        raise HTTPException(status_code=403, detail="An active subscription is required to share credits.")

    plan = _get_plan(sub, db)
    if not plan or plan.id == "free":
        raise HTTPException(status_code=403, detail="Free plan users cannot share credits.")

    credit = db.query(Credit).filter(Credit.user_id == user.id).first()
    if not credit:
        raise HTTPException(status_code=404, detail="Credit record not found.")

    breakdown = _compute_shareable_balance(sub, plan, credit)

    referees = db.query(User).filter(User.referrer_id == user.id).all()
    referred_list = []
    for r in referees:
        referred_list.append({
            "uid": r.firebase_uid or "",
            "display_name": r.display_name or r.email.split("@")[0],
            "email_hint": (r.email[:3] + "***" + r.email[r.email.find("@"):])
                          if "@" in r.email else r.email[:3] + "***",
        })

    return {
        "shareable_balance": round(breakdown["total_shareable"], 2),
        "quota_bank": round(breakdown["quota_bank"], 2),
        "current_cycle_balance": round(breakdown["current_cycle_balance"], 2),
        "unallocated": round(breakdown["unallocated"], 2),
        "remaining_cycles": breakdown["remaining_cycles"],
        "cycle_allowance": round(breakdown["cycle_allowance"], 4),
        "regular_plan_credits": round(breakdown["regular_plan_credits"], 2),
        "plan_name": plan.display_name,
        "plan_id": plan.id,
        "referred_users": referred_list,
    }


@router.post("/api/quota-share/preview")
def quota_share_preview(
    req: QuotaSharePreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user),
):
    """
    Dry-run preview: calculates deductions without committing anything.
    Returns a detailed transfer summary for display in the CLI confirmation step.
    """
    sub = _get_active_sub(user, db)
    if not sub:
        raise HTTPException(status_code=403, detail="An active subscription is required to share credits.")
    plan = _get_plan(sub, db)
    if not plan or plan.id == "free":
        raise HTTPException(status_code=403, detail="Free plan users cannot share credits.")
    credit = db.query(Credit).filter(Credit.user_id == user.id).first()
    if not credit:
        raise HTTPException(status_code=404, detail="Credit record not found.")

    breakdown = _compute_shareable_balance(sub, plan, credit)
    if req.amount > breakdown["total_shareable"]:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient shareable balance. Available: {round(breakdown['total_shareable'], 2)} credits.",
        )

    if not req.recipient_uid:
        raise HTTPException(status_code=400, detail="Recipient UID is required.")
    
    if req.recipient_uid == "redeem_code_only":
        recipient_info = {
            "uid": "redeem_code_only",
            "display_name": "Create Redeem Code",
            "email_hint": "Deducts shareable credits to create a claimable UTIM-XXXX code",
        }
    else:
        if req.recipient_uid == (user.firebase_uid or ""):
            raise HTTPException(status_code=400, detail="You cannot share credits with yourself.")

        recipient = db.query(User).filter(User.firebase_uid == req.recipient_uid).first()
        if not recipient:
            raise HTTPException(status_code=404, detail="Recipient not found.")
        if recipient.referrer_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You can only share credits with users you have directly referred.",
            )
        recipient_info = {
            "uid": recipient.firebase_uid or "",
            "display_name": recipient.display_name or recipient.email.split("@")[0],
            "email_hint": (recipient.email[:3] + "***" + recipient.email[recipient.email.find("@"):])
                          if "@" in recipient.email else recipient.email[:3] + "***",
        }

    deductions = _compute_deductions(req.amount, breakdown)
    new_cycle_quota = _future_cycle_quota(breakdown, deductions["from_unallocated"])
    remaining_shareable = breakdown["total_shareable"] - req.amount
    new_unallocated = max(0.0, breakdown["unallocated"] - deductions["from_unallocated"])

    return {
        "recipient": recipient_info,
        "amount": round(req.amount, 2),
        "deductions": {
            "from_quota_bank": round(deductions["from_bank"], 2),
            "from_current_cycle": round(deductions["from_cycle"], 2),
            "from_unallocated": round(deductions["from_unallocated"], 2),
        },
        "remaining_shareable": round(remaining_shareable, 2),
        "remaining_unallocated": round(new_unallocated, 2),
        "new_cycle_quota": round(new_cycle_quota, 4) if new_cycle_quota is not None else None,
        "remaining_cycles": breakdown["remaining_cycles"],
        "regular_plan_credits": round(breakdown["regular_plan_credits"], 2),
        "plan_name": plan.display_name,
    }


@router.post("/api/quota-share/transfer")
def quota_share_transfer(
    req: QuotaShareTransferRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user),
):
    """
    Deducts credits from the sender's account in priority order, generates an
    irrevocable RedeemCode, and returns it to the caller.

    The code can be redeemed by:
      • Any user who was directly referred by the sender
      • The sender themselves

    The redeemed credits are added to the claimer's bonus_balance.
    Codes never expire and cannot be revoked.
    """
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Transfer amount must be greater than zero.")

    # Sender validation
    sub = _get_active_sub(user, db)
    if not sub:
        raise HTTPException(status_code=403, detail="An active subscription is required to share credits.")
    plan = _get_plan(sub, db)
    if not plan or plan.id == "free":
        raise HTTPException(status_code=403, detail="Free plan users cannot share credits.")

    # Recipient validation
    if not req.recipient_uid:
        raise HTTPException(status_code=400, detail="Recipient UID is required.")

    is_direct = (req.recipient_uid != "redeem_code_only")
    recipient = None

    if is_direct:
        if req.recipient_uid == (user.firebase_uid or ""):
            raise HTTPException(status_code=400, detail="You cannot share credits with yourself.")

        recipient = db.query(User).filter(User.firebase_uid == req.recipient_uid).first()
        if not recipient:
            raise HTTPException(status_code=404, detail="Recipient not found.")
        if recipient.referrer_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You can only share credits with users you have directly referred.",
            )

    try:
        # Lock sender credit row to prevent concurrent double-spend
        sender_credit = (
            db.query(Credit)
            .filter(Credit.user_id == user.id)
            .with_for_update()
            .first()
        )
        if not sender_credit:
            raise HTTPException(status_code=404, detail="Sender credit record not found.")

        breakdown = _compute_shareable_balance(sub, plan, sender_credit)
        if req.amount > breakdown["total_shareable"]:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient shareable balance. Available: {round(breakdown['total_shareable'], 2)} credits.",
            )

        deductions = _compute_deductions(req.amount, breakdown)

        # 1. Deduct from Quota Bank
        sender_credit.balance = max(0.0, (sender_credit.balance or 0.0) - deductions["from_bank"])

        # 2. Deduct from current cycle
        if deductions["from_cycle"] > 0:
            sub.current_cycle_used = (sub.current_cycle_used or 0.0) + deductions["from_cycle"]

        # 3. Deduct from unallocated → recalculate future cycle quota
        new_cycle_quota = None
        if deductions["from_unallocated"] > 0:
            new_unallocated = max(0.0, breakdown["unallocated"] - deductions["from_unallocated"])
            remaining_cycles = max(1, breakdown["remaining_cycles"])
            new_cycle_quota = new_unallocated / remaining_cycles
            sub.refill_rate_override = round(new_cycle_quota, 4)

        now = datetime.datetime.utcnow()
        billing_cycle_start = sub.current_period_start or now
        code_str = None

        if is_direct:
            # Credit the recipient's bonus_balance directly
            recipient_credit = (
                db.query(Credit)
                .filter(Credit.user_id == recipient.id)
                .with_for_update()
                .first()
            )
            if not recipient_credit:
                recipient_credit = Credit(
                    user_id=recipient.id,
                    balance=0.0,
                    bonus_balance=0.0,
                    bonus_limit=0.0,
                    total_spent=0.0,
                    total_topped_up=0.0,
                )
                db.add(recipient_credit)
                db.flush()

            # Determine bonus cap for recipient's plan
            recipient_sub = _get_active_sub(recipient, db)
            recipient_plan = _get_plan(recipient_sub, db) if recipient_sub else None
            recipient_plan_id = recipient_plan.id if recipient_plan else "free"
            bonus_cap = get_max_bonus_limit(recipient_plan_id)

            current_bonus = recipient_credit.bonus_balance or 0.0
            current_bonus_limit = recipient_credit.bonus_limit or 0.0

            # Add the credits (cap at plan bonus limit)
            space_available = max(0.0, bonus_cap - current_bonus)
            credits_to_add = min(req.amount, space_available) if bonus_cap > 0 else req.amount

            recipient_credit.bonus_balance = current_bonus + credits_to_add
            recipient_credit.bonus_limit = min(bonus_cap, current_bonus_limit + credits_to_add)
        else:
            # Generate a unique redeem code
            code_str = _generate_redeem_code()
            # Collision guard (astronomically unlikely but safe)
            while db.query(RedeemCode).filter(RedeemCode.code == code_str).first():
                code_str = _generate_redeem_code()

            redeem_code = RedeemCode(
                id=str(uuid.uuid4()),
                code=code_str,
                sender_id=user.id,
                intended_recipient_id=None,
                amount=req.amount,
                from_quota_bank=deductions["from_bank"],
                from_current_cycle=deductions["from_cycle"],
                from_unallocated=deductions["from_unallocated"],
                billing_cycle_start=billing_cycle_start,
                is_redeemed=False,
                redeemed_by_id=None,
                redeemed_at=None,
                created_at=now,
            )
            db.add(redeem_code)

        # Audit record
        transfer_record = QuotaTransfer(
            id=str(uuid.uuid4()),
            sender_id=user.id,
            recipient_id=recipient.id if is_direct else None,
            amount=req.amount,
            from_quota_bank=deductions["from_bank"],
            from_current_cycle=deductions["from_cycle"],
            from_unallocated=deductions["from_unallocated"],
            billing_cycle_start=billing_cycle_start,
            created_at=now,
        )
        db.add(transfer_record)

        db.commit()
        db.refresh(sender_credit)

        logger.info(
            f"quota_share_transfer sender={user.id} recipient={recipient.id if is_direct else 'redeem_code'} "
            f"amount={req.amount} code={code_str} bank={deductions['from_bank']} "
            f"cycle={deductions['from_cycle']} unallocated={deductions['from_unallocated']}"
        )

        new_breakdown = _compute_shareable_balance(sub, plan, sender_credit)
        return {
            "success": True,
            "redeem_code": code_str,
            "direct_transfer": is_direct,
            "transfer_id": transfer_record.id,
            "amount": round(req.amount, 2),
            "recipient": {
                "uid": "redeem_code_only" if not is_direct else (recipient.firebase_uid or ""),
                "display_name": "Create Redeem Code" if not is_direct else (recipient.display_name or recipient.email.split("@")[0]),
            },
            "deductions": {
                "from_quota_bank": round(deductions["from_bank"], 2),
                "from_current_cycle": round(deductions["from_cycle"], 2),
                "from_unallocated": round(deductions["from_unallocated"], 2),
            },
            "new_cycle_quota": round(new_cycle_quota, 4) if new_cycle_quota is not None else None,
            "remaining_shareable": round(new_breakdown["total_shareable"], 2),
            "remaining_unallocated": round(new_breakdown["unallocated"], 2),
            "remaining_cycles": new_breakdown["remaining_cycles"],
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"quota_share_transfer_error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transfer failed: {str(exc)}")


@router.get("/api/quota-share/redeem/{code}")
def redeem_code_lookup(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user),
):
    """
    Look up a redeem code's details without claiming it.
    Used by the CLI to show a preview before the user confirms.
    """
    code_upper = code.strip().upper()
    rc = db.query(RedeemCode).filter(RedeemCode.code == code_upper).first()
    if not rc:
        raise HTTPException(status_code=404, detail="Redeem code not found.")

    if rc.is_redeemed:
        raise HTTPException(status_code=409, detail="This redeem code has already been used.")

    # Eligibility check: must be a direct referee of the sender, or the sender themselves
    is_eligible = (
        user.id == rc.sender_id
        or user.referrer_id == rc.sender_id
    )
    if not is_eligible:
        raise HTTPException(
            status_code=403,
            detail="You are not eligible to redeem this code. "
                   "Only directly referred users of the code creator can redeem it.",
        )

    sender = db.query(User).filter(User.id == rc.sender_id).first()
    return {
        "code": rc.code,
        "amount": round(rc.amount, 2),
        "is_redeemed": rc.is_redeemed,
        "sender_name": (sender.display_name or sender.email.split("@")[0]) if sender else "Unknown",
        "created_at": rc.created_at.isoformat() if rc.created_at else None,
    }


@router.post("/api/quota-share/redeem")
def redeem_quota_code(
    req: RedeemCodeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user),
):
    """
    Redeem a quota share code.
    Credits are added to the caller's bonus_balance (Bonus Quota bar).

    Eligibility:
      • Must be a direct referee of the code's creator
      • OR the code creator themselves

    Codes never expire and cannot be revoked. Each code can only be redeemed once.
    """
    code_upper = req.code.strip().upper()

    try:
        # Lock the redeem code row to prevent race conditions
        rc = (
            db.query(RedeemCode)
            .filter(RedeemCode.code == code_upper)
            .with_for_update()
            .first()
        )
        if not rc:
            raise HTTPException(status_code=404, detail="Redeem code not found. Please check the code and try again.")

        if rc.is_redeemed:
            raise HTTPException(status_code=409, detail="This redeem code has already been used.")

        # Eligibility check
        is_eligible = (
            user.id == rc.sender_id
            or user.referrer_id == rc.sender_id
        )
        if not is_eligible:
            raise HTTPException(
                status_code=403,
                detail="You are not eligible to redeem this code. "
                       "Only directly referred users of the code creator can redeem it.",
            )

        # Credit the claimer's bonus_balance
        claimer_credit = (
            db.query(Credit)
            .filter(Credit.user_id == user.id)
            .with_for_update()
            .first()
        )
        if not claimer_credit:
            claimer_credit = Credit(
                user_id=user.id,
                balance=0.0,
                bonus_balance=0.0,
                bonus_limit=0.0,
                total_spent=0.0,
                total_topped_up=0.0,
            )
            db.add(claimer_credit)
            db.flush()

        # Determine bonus cap for claimer's plan
        claimer_sub = _get_active_sub(user, db)
        claimer_plan = _get_plan(claimer_sub, db) if claimer_sub else None
        claimer_plan_id = claimer_plan.id if claimer_plan else "free"
        bonus_cap = get_max_bonus_limit(claimer_plan_id)

        current_bonus = claimer_credit.bonus_balance or 0.0
        current_bonus_limit = claimer_credit.bonus_limit or 0.0

        # Add the credits (cap at plan bonus limit)
        space_available = max(0.0, bonus_cap - current_bonus)
        credits_to_add = min(rc.amount, space_available) if bonus_cap > 0 else rc.amount

        claimer_credit.bonus_balance = current_bonus + credits_to_add
        claimer_credit.bonus_limit = min(bonus_cap, current_bonus_limit + credits_to_add)

        # Mark code as redeemed
        now = datetime.datetime.utcnow()
        rc.is_redeemed = True
        rc.redeemed_by_id = user.id
        rc.redeemed_at = now

        db.commit()

        sender = db.query(User).filter(User.id == rc.sender_id).first()

        logger.info(
            f"quota_redeem code={rc.code} claimer={user.id} "
            f"amount={rc.amount} credited={credits_to_add} plan={claimer_plan_id}"
        )

        return {
            "success": True,
            "code": rc.code,
            "credits_added": round(credits_to_add, 2),
            "amount_in_code": round(rc.amount, 2),
            "capped": credits_to_add < rc.amount,
            "new_bonus_balance": round(claimer_credit.bonus_balance, 2),
            "bonus_cap": round(bonus_cap, 2),
            "sender_name": (sender.display_name or sender.email.split("@")[0]) if sender else "Unknown",
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"quota_redeem_error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Redeem failed: {str(exc)}")


@router.get("/api/quota-share/history")
def quota_share_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user),
):
    """
    Returns the last 20 sent and received quota transfers for the current user,
    along with any redeem codes the user has created (sent) or redeemed (received).
    """
    sent = (
        db.query(QuotaTransfer)
        .filter(QuotaTransfer.sender_id == user.id)
        .order_by(QuotaTransfer.created_at.desc())
        .limit(20)
        .all()
    )
    received = (
        db.query(QuotaTransfer)
        .filter(QuotaTransfer.recipient_id == user.id)
        .order_by(QuotaTransfer.created_at.desc())
        .limit(20)
        .all()
    )

    # Codes created by this user
    codes_sent = (
        db.query(RedeemCode)
        .filter(RedeemCode.sender_id == user.id)
        .order_by(RedeemCode.created_at.desc())
        .limit(20)
        .all()
    )

    # Codes redeemed by this user
    codes_redeemed = (
        db.query(RedeemCode)
        .filter(RedeemCode.redeemed_by_id == user.id)
        .order_by(RedeemCode.redeemed_at.desc())
        .limit(20)
        .all()
    )

    def _fmt_transfer(t: QuotaTransfer, direction: str) -> dict:
        other_id = t.recipient_id if direction == "sent" else t.sender_id
        other = db.query(User).filter(User.id == other_id).first()
        return {
            "id": t.id,
            "direction": direction,
            "amount": round(t.amount, 2),
            "other_user": (other.display_name or other.email.split("@")[0]) if other else "Unknown",
            "from_quota_bank": round(t.from_quota_bank or 0.0, 2),
            "from_current_cycle": round(t.from_current_cycle or 0.0, 2),
            "from_unallocated": round(t.from_unallocated or 0.0, 2),
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }

    def _fmt_code(rc: RedeemCode, direction: str) -> dict:
        other_id = rc.redeemed_by_id if direction == "created" else rc.sender_id
        other = db.query(User).filter(User.id == other_id).first() if other_id else None
        return {
            "code": rc.code,
            "direction": direction,
            "amount": round(rc.amount, 2),
            "is_redeemed": rc.is_redeemed,
            "other_user": (other.display_name or other.email.split("@")[0]) if other else None,
            "created_at": rc.created_at.isoformat() if rc.created_at else None,
            "redeemed_at": rc.redeemed_at.isoformat() if rc.redeemed_at else None,
        }

    return {
        "transfers_sent": [_fmt_transfer(t, "sent") for t in sent],
        "transfers_received": [_fmt_transfer(t, "received") for t in received],
        "codes_created": [_fmt_code(rc, "created") for rc in codes_sent],
        "codes_redeemed": [_fmt_code(rc, "redeemed") for rc in codes_redeemed],
    }
