"""
Routes: /quota, /plans, and /subscribe — Quota status, usage limits, and product plan tiers
"""
from __future__ import annotations

import base64
import datetime
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import Plan, QuotaUsage, User, UserSubscription, get_db, get_max_bonus_limit
from ..auth import get_current_user, get_current_firebase_user
from .completion_routes import get_or_create_quota

router = APIRouter(tags=["quota"])
logger = logging.getLogger("utim.routes.quota")

# Razorpay Keys & Default Plan IDs
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")

def get_razorpay_plan_id(plan_name: str, interval: str = "monthly", currency: str = "INR") -> Optional[str]:
    name = plan_name.upper().strip()
    curr = currency.upper().strip()
    
    # Gather potential environment variable keys in order of priority
    keys_to_check = []
    
    if curr == "USD":
        if name in ("ULTIMATE", "MAX_PREMIUM", "MAX9999", "MAX_NODE"):
            keys_to_check = [
                "RAZORPAY_PLAN_ULTIMATE_USD",
                "RAZORPAY_ULTIMATE_USD"
            ]
        elif name in ("MAX", "PROFESSIONAL", "PROMAX", "PROFESSIONAL_CORE"):
            keys_to_check = [
                "RAZORPAY_PLAN_PROFESSIONAL_USD",
                "RAZORPAY_PROFESSIONAL_USD"
            ]
        elif name in ("PRO", "STARTER", "STARTER_NODE"):
            keys_to_check = [
                "RAZORPAY_PLAN_STARTER_USD",
                "RAZORPAY_STARTER_USD"
            ]
        elif name in ("HOBBY", "HOBBY1", "HOBBYIST", "HOBBYIST_NODE"):
            keys_to_check = [
                "RAZORPAY_PLAN_HOBBY_USD",
                "RAZORPAY_HOBBY_USD"
            ]
        # Fallbacks for USD
        keys_to_check.append(f"RAZORPAY_PLAN_{name}_USD")
        keys_to_check.append(f"RAZORPAY_{name}_USD")
    else:
        # Currency is INR
        if name in ("ULTIMATE", "MAX_PREMIUM", "MAX9999", "MAX_NODE"):
            keys_to_check = [
                "RAZORPAY_PRO_MAX",
                "RAZORPAY_PLAN_PRO_MAX",
                "RAZORPAY_PLAN_ULTIMATE",
                "RAZORPAY_ULTIMATE"
            ]
        elif name in ("MAX", "PROFESSIONAL", "PROMAX", "PROFESSIONAL_CORE"):
            keys_to_check = [
                "RAZORPAY_PLAN_MAX",
                "RAZORPAY_MAX",
                "RAZORPAY_PLAN_PROFESSIONAL",
                "RAZORPAY_PROFESSIONAL"
            ]
        elif name in ("PRO", "STARTER", "STARTER_NODE"):
            keys_to_check = [
                "RAZORPAY_PLAN_PRO",
                "RAZORPAY_PRO",
                "RAZORPAY_PLAN_STARTER",
                "RAZORPAY_STARTER"
            ]
        elif name in ("HOBBY", "HOBBY1", "HOBBYIST", "HOBBYIST_NODE"):
            keys_to_check = [
                "RAZORPAY_PLAN_HOBBY",
                "RAZORPAY_HOBBY",
                "RAZORPAY_PLAN_HOBBY1",
                "RAZORPAY_HOBBY1"
            ]
        # Fallbacks for INR
        keys_to_check.append(f"RAZORPAY_PLAN_{name}")
        keys_to_check.append(f"RAZORPAY_{name}")
        
    # Lookup the keys in environment
    for key in keys_to_check:
        val = os.environ.get(key)
        if val:
            return val
            
    return None


def get_plan_usd_price(plan_name: str) -> float:
    name = plan_name.upper().strip()
    if name in ("ULTIMATE", "MAX_PREMIUM", "MAX9999", "MAX_NODE"):
        return 110.0
    elif name in ("MAX", "PROFESSIONAL", "PROMAX", "PROFESSIONAL_CORE"):
        return 55.0
    elif name in ("PRO", "STARTER", "STARTER_NODE"):
        return 25.0
    elif name in ("HOBBY", "HOBBY1", "HOBBYIST", "HOBBYIST_NODE"):
        return 7.0
    return 0.0


def create_razorpay_link(user_id: str, email: str, plan_name: str, amount_inr: int, currency: str = "INR") -> str:
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    # Use mock checkout if Razorpay credentials are not provided
    if not key_id or key_id == "mock_key_id":
        server_url = os.environ.get("SERVER_URL", "http://localhost:8000")
        return f"{server_url}/billing/mock-checkout?user_id={user_id}&plan_id={plan_name}"

    import requests

    # Check if a Razorpay Subscription Plan ID is configured for this plan
    env_plan_id = get_razorpay_plan_id(plan_name, currency=currency)
    if env_plan_id:
        url = "https://api.razorpay.com/v1/subscriptions"
        auth_str = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/json"
        }
        payload = {
            "plan_id": env_plan_id,
            "total_count": 12,
            "quantity": 1,
            "customer_notify": 1,
            "notes": {
                "user_id": user_id,
                "plan_id": plan_name,
                "currency": currency
            }
        }
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        res_data = response.json()
        return res_data.get("short_url") or f"https://rzp.io/i/{res_data['id']}"

    # Fallback to payment links
    url = "https://api.razorpay.com/v1/payment_links"
    auth_str = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_str}",
        "Content-Type": "application/json"
    }

    server_url = os.environ.get("SERVER_URL", "https://api.utim.dev")

    if currency.upper() == "USD":
        amount_cents = int(get_plan_usd_price(plan_name) * 100)
        payload = {
            "amount": amount_cents,
            "currency": "USD",
            "accept_partial": False,
            "reference_id": f"sub_{uuid.uuid4().hex[:12]}",
            "description": f"UTIM {plan_name.capitalize()} Subscription",
            "customer": {
                "name": email.split("@")[0],
                "email": email,
            },
            "notify": {
                "sms": False,
                "email": True
            },
            "callback_url": f"{server_url}/billing/success?user_id={user_id}&plan_id={plan_name}",
            "callback_method": "get"
        }
    else:
        amount_inr_paise = int(amount_inr * 100)
        payload = {
            "amount": amount_inr_paise,
            "currency": "INR",
            "accept_partial": False,
            "reference_id": f"sub_{uuid.uuid4().hex[:12]}",
            "description": f"UTIM {plan_name.capitalize()} Subscription",
            "customer": {
                "name": email.split("@")[0],
                "email": email,
            },
            "notify": {
                "sms": False,
                "email": True
            },
            "callback_url": f"{server_url}/billing/success?user_id={user_id}&plan_id={plan_name}",
            "callback_method": "get"
        }

    response = requests.post(url, json=payload, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()["short_url"]


def verify_payment_link(link_id: str) -> bool:
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    if not key_id or key_id == "mock_key_id":
        return True

    import requests

    url = f"https://api.razorpay.com/v1/payment_links/{link_id}"
    auth_str = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_str}",
    }
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        return response.json().get("status") == "paid"
    return False


def verify_subscription(sub_id: str) -> bool:
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    if not key_id or key_id == "mock_key_id":
        return True

    import requests

    url = f"https://api.razorpay.com/v1/subscriptions/{sub_id}"
    auth_str = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_str}",
    }
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        status = response.json().get("status")
        return status in ("active", "authenticated")
    return False


def activate_subscription(db: Session, user_id: str, plan_id: str, razorpay_sub_id: str = None, razorpay_cust_id: str = None, interval: str = "monthly"):
    import uuid
    from ..db import Credit, Transaction, UsedEmailBonus, get_max_bonus_limit

    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise ValueError(f"Plan {plan_id} not found")

    sub = db.query(UserSubscription).filter(UserSubscription.user_id == user_id).first()
    now = datetime.datetime.utcnow()
    end_date = now + datetime.timedelta(days=365 if interval == "yearly" else 30)

    # Detect if this is a downgrade
    prev_plan_credits = 0.0
    prev_plan_id = None
    if sub and sub.plan:
        prev_plan_credits = sub.plan.credits_per_month
        prev_plan_id = sub.plan.id

    is_downgrade = False
    if prev_plan_credits > plan.credits_per_month:
        is_downgrade = True

    if not sub:
        sub = UserSubscription(
            user_id=user_id,
            plan_id=plan.id,
            status="active",
            current_period_start=now,
            current_period_end=end_date,
            razorpay_subscription_id=razorpay_sub_id,
            razorpay_customer_id=razorpay_cust_id,
            refills_processed=0,
            last_refill_at=None
        )
        db.add(sub)
    else:
        sub.plan_id = plan.id
        sub.status = "active"
        sub.current_period_start = now
        sub.current_period_end = end_date
        sub.refills_processed = 0
        sub.last_refill_at = None
        if razorpay_sub_id:
            sub.razorpay_subscription_id = razorpay_sub_id
        if razorpay_cust_id:
            sub.razorpay_customer_id = razorpay_cust_id

    # Adjust credit balance / roll over quota
    credit = db.query(Credit).filter(Credit.user_id == user_id).first()
    max_limit = plan.credits_per_month * 2.0
    
    if credit:
        old_balance = credit.balance
        # Ensure bonus fields exist
        if not hasattr(credit, "bonus_balance") or credit.bonus_balance is None:
            credit.bonus_balance = 0.0
        if not hasattr(credit, "bonus_limit") or credit.bonus_limit is None:
            credit.bonus_limit = 0.0
            
        # Capping the current balance to the new plan tier limit
        max_bonus = get_max_bonus_limit(plan.id)
        credit.bonus_balance = min(max_bonus, credit.bonus_balance)
        credit.bonus_limit = min(max_bonus, credit.bonus_limit)

        if is_downgrade:
            # Special check: from pro to hobby
            if prev_plan_id == "pro" and plan.id == "hobby":
                # they get $7 in quota bank of hobby plan (7000 credits)
                # and the rest (old_balance - 7000) of professional plan gets halved and goes in the bonus quota
                quota_bank = 7000.0
                if old_balance > quota_bank:
                    rest = old_balance - quota_bank
                    bonus_added = rest * 0.5
                    credit.balance = quota_bank
                    credit.bonus_balance = min(max_bonus, (credit.bonus_balance or 0.0) + bonus_added)
                    credit.bonus_limit = min(max_bonus, (credit.bonus_limit or 0.0) + bonus_added)
                    
                    tx = Transaction(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        kind="deduction",
                        amount=-(old_balance - quota_bank),
                        balance_after=quota_bank,
                        description=f"Downgrade to Hobby: Quota bank capped at $7.00, remaining {rest/1000.0:.2f} USD converted to Bonus Quota at 50% rate"
                    )
                    db.add(tx)
                    
                    # Trigger bonus credits email in background thread
                    user_row = db.query(User).filter(User.id == user_id).first()
                    if user_row and user_row.email:
                        from ..db import EmailTracking
                        tracking = db.query(EmailTracking).filter(EmailTracking.user_id == user_id).first()
                        now_utc = datetime.datetime.utcnow()
                        if not tracking or not tracking.bonus_email_sent_at or (now_utc - tracking.bonus_email_sent_at).total_seconds() > 600:
                            if tracking:
                                tracking.bonus_email_sent_at = now_utc
                                db.commit()

                            from ..email_utils import send_bonus_credits_email
                            import threading
                            def send_bonus_bg(email, name, amount):
                                from ..db import SessionLocal
                                thread_db = SessionLocal()
                                try:
                                    success = send_bonus_credits_email(email, name, amount)
                                    if not success:
                                        t_track = thread_db.query(EmailTracking).filter(EmailTracking.user_id == user_id).first()
                                        if t_track:
                                            t_track.bonus_email_sent_at = None
                                            thread_db.commit()
                                except Exception as e:
                                    logger.error(f"Error sending bonus email in thread: {e}")
                                finally:
                                    thread_db.close()
                            threading.Thread(
                                target=send_bonus_bg,
                                args=(user_row.email, user_row.display_name or user_row.email.split("@")[0], bonus_added),
                                daemon=True
                            ).start()
                else:
                    credit.balance = old_balance
            else:
                # Regular downgrade logic: keep bank limit + 50% of the excess
                if old_balance > max_limit:
                    excess = old_balance - max_limit
                    new_balance = max_limit + (excess * 0.5)
                    credit.balance = new_balance
                    deduction = old_balance - new_balance
                    tx = Transaction(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        kind="deduction",
                        amount=-deduction,
                        balance_after=new_balance,
                        description=f"Quota downgrade cap applied: kept {max_limit/1000.0:.2f} USD + 50% of excess"
                    )
                    db.add(tx)
        else:
            # ── Upgrade from Free plan: wipe free-tier balance ──────────────
            # The free plan's credit "tank" (max 100 credits = $0.10) is a
            # rate-limited, non-rollover allowance. It is NOT earned quota and
            # must NOT be carried into the paid plan's quota bank.
            if prev_plan_id == "free" and plan.id != "free":
                if old_balance > 0:
                    tx = Transaction(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        kind="deduction",
                        amount=-old_balance,
                        balance_after=0.0,
                        description=(
                            f"Free plan balance wiped on upgrade to {plan.display_name}: "
                            f"free-tier allowance does not carry over to paid plans"
                        )
                    )
                    db.add(tx)
                credit.balance = 0.0
            # Same plan or regular (paid→paid) upgrade: cap at new max bank limit
            elif old_balance > max_limit:
                credit.balance = max_limit
                deduction = old_balance - max_limit
                tx = Transaction(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    kind="deduction",
                    amount=-deduction,
                    balance_after=max_limit,
                    description=f"Quota bank limit cap applied on {plan.name.title()} Plan activation"
                )
                db.add(tx)
    else:
        credit = Credit(user_id=user_id, balance=0.0, bonus_balance=0.0, bonus_limit=0.0, total_topped_up=0.0)
        db.add(credit)

    # First purchase bonus allocation
    user_row = db.query(User).filter(User.id == user_id).first()
    user_email = user_row.email if user_row else ""

    bonus_desc = f"First Purchase Bonus ({plan.display_name} Plan)"
    bonus_descs = [bonus_desc]
    if plan.id == "hobby":
        bonus_descs.append("First Purchase Bonus (Hobby Plan)")
        bonus_descs.append("First Purchase Bonus (Hobbyist Node Plan)")
    elif plan.id == "pro":
        bonus_descs.append("First Purchase Bonus (Pro Plan)")
        bonus_descs.append("First Purchase Bonus (Starter Node Plan)")
    elif plan.id == "max":
        bonus_descs.append("First Purchase Bonus (Max Plan)")
        bonus_descs.append("First Purchase Bonus (Professional Core Plan)")
    elif plan.id == "ultimate":
        bonus_descs.append("First Purchase Bonus (Ultimate Core Plan)")
        bonus_descs.append("First Purchase Bonus (MAX Node Plan)")

    has_bonus = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.description.in_(bonus_descs)
    ).first()

    has_claimed_by_email = False
    if user_email:
        has_claimed_by_email = db.query(UsedEmailBonus).filter(
            UsedEmailBonus.email == user_email.lower().strip(),
            UsedEmailBonus.plan_id == plan.id
        ).first() is not None

    is_same_plan_renewal = (prev_plan_id == plan.id)

    if not is_same_plan_renewal and not has_bonus and not has_claimed_by_email and plan.id in ("hobby", "pro", "max", "ultimate"):
        bonus_map = {
            "hobby": 500.0,
            "pro": 2000.0,
            "max": 5000.0,
            "ultimate": 12000.0
        }
        bonus_amt = bonus_map.get(plan.id, 0.0)
        if bonus_amt > 0:
            max_bonus = get_max_bonus_limit(plan.id)
            credit.bonus_balance = min(max_bonus, credit.bonus_balance + bonus_amt)
            credit.bonus_limit = min(max_bonus, credit.bonus_limit + bonus_amt)
            
            # Record email bonus claim to block delete-recreate abuse
            if user_email:
                used_bonus = UsedEmailBonus(
                    email=user_email.lower().strip(),
                    plan_id=plan.id
                )
                db.add(used_bonus)

            tx_bonus = Transaction(
                id=str(uuid.uuid4()),
                user_id=user_id,
                kind="refill",
                amount=bonus_amt,
                balance_after=credit.balance,
                description=bonus_desc
            )
            db.add(tx_bonus)

    quota = db.query(QuotaUsage).filter(
        QuotaUsage.user_id == user_id,
        QuotaUsage.period_start <= now,
        QuotaUsage.period_end >= now
    ).first()

    if not quota:
        quota = QuotaUsage(
            user_id=user_id,
            period_start=now,
            period_end=end_date,
            credits_used=0.0,
            credits_limit=plan.credits_per_month,
            reset_at=end_date,
        )
        db.add(quota)
    else:
        quota.credits_limit = plan.credits_per_month
        quota.reset_at = end_date
        quota.credits_used = 0.0
        quota.period_start = now
        quota.period_end = end_date

    # Reset/consume user's referral discount for this plan (as it has been applied to this purchase/renewal)
    try:
        from .referral_routes import consume_referral_discount
        consume_referral_discount(db, referrer_id=user_id, plan_id=plan.id)
    except Exception as _ref_err:
        logger.warning(f"referral_consume_failed user={user_id} plan={plan.id}: {_ref_err}")

    db.commit()
    logger.info("subscription_activated", extra={
        "user_id": user_id,
        "plan_id": plan_id,
        "credits_limit": plan.credits_per_month,
        "razorpay_sub_id": razorpay_sub_id,
        "razorpay_cust_id": razorpay_cust_id
    })


# ── Schemas ───────────────────────────────────────────────────────────────────

class SubscribeRequest(BaseModel):
    plan_id: str  # "hobby", "pro", "max", "ultimate"
    currency: Optional[str] = "INR"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/quota", summary="Get the current billing period's quota usage and plan info")
def get_quota(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user),
):
    quota = get_or_create_quota(db, user)
    sub = user.subscription
    plan = sub.plan if sub else None
    if not plan:
        plan = db.query(Plan).filter(Plan.id == (sub.plan_id if sub else "free")).first()

    now = datetime.datetime.utcnow()
    days_until_reset = max(0, (quota.reset_at - now).days)
    percent_used = round((quota.credits_used / quota.credits_limit) * 100, 1) if quota.credits_limit > 0 else 100.0

    from ..db import Credit
    cr = db.query(Credit).filter(Credit.user_id == user.id).first()
    bonus_balance = getattr(cr, "bonus_balance", 0.0) or 0.0

    # Resolve allowed models list
    models_allowed: List[str] = []
    if bonus_balance > 0.0:
        models_allowed = ["all"]
    else:
        allowed_models_str = plan.allowed_models if plan else "free"
        if allowed_models_str == "all":
            models_allowed = ["all"]
        else:
            tokens = [t.strip() for t in allowed_models_str.split(",")]
            for t in tokens:
                if t == "free":
                    from ..models import MODEL_REGISTRY
                    for m_id, m_entry in MODEL_REGISTRY.items():
                        if "free" in m_entry.tags or m_id.endswith(":free"):
                            models_allowed.append(m_id)
                else:
                    models_allowed.append(t)

    heavy_calls_available = (quota.credits_used < quota.credits_limit)

    five_hour_quota_exhausted = False
    five_hour_reset_at = None
    free_monthly_remaining = None
    free_bonus_balance = 0.0
    bonus_limit = 0.0
    free_bonus_percent = 0.0

    if plan and plan.id == "free":
        free_monthly_used = getattr(cr, "free_monthly_used", 0.0) or 0.0
        free_bonus_balance = getattr(cr, "bonus_balance", 0.0) or 0.0
        bonus_limit = getattr(cr, "bonus_limit", 0.0) or 0.0
        FREE_MONTHLY_CAP = 3000.0
        free_monthly_remaining = max(0.0, FREE_MONTHLY_CAP - free_monthly_used)
        if bonus_limit > 0.0:
            free_bonus_percent = min(100.0, (free_bonus_balance / bonus_limit) * 100.0)
            
        # Enforce correct Free plan limit display (overriding the DB 1000 limit)
        quota.credits_limit = FREE_MONTHLY_CAP
        percent_used = round((free_monthly_used / FREE_MONTHLY_CAP) * 100, 1)
        heavy_calls_available = (free_monthly_used < FREE_MONTHLY_CAP)
        
        # Free plan 5-hour quota exhaustion check
        balance = getattr(cr, "balance", 0.0)
        if (balance + free_bonus_balance) <= 0.0:
            five_hour_quota_exhausted = True
            refill_interval = 5 * 3600
            period_start = sub.current_period_start if sub else now
            elapsed_in_window = (now - period_start).total_seconds() % refill_interval
            refill_remaining_seconds = int(refill_interval - elapsed_in_window)
            refill_time = now + datetime.timedelta(seconds=refill_remaining_seconds)
            five_hour_reset_at = refill_time.isoformat() + "Z"

    elif plan and plan.id != "free" and sub:
        cycle_allowance = plan.credits_per_month / 144.0
        current_cycle_used = sub.current_cycle_used or 0.0
        if current_cycle_used >= cycle_allowance:
            from ..db import Credit
            credit_row = db.query(Credit).filter(Credit.user_id == user.id).first()
            balance = credit_row.balance if credit_row else 0.0
            bonus_balance = getattr(credit_row, "bonus_balance", 0.0) or 0.0
            if (balance + bonus_balance) <= 0.0:
                five_hour_quota_exhausted = True
                
                # Calculate next refill time
                refill_interval = 5 * 3600
                period_start = sub.current_period_start or sub.created_at or now
                elapsed_in_window = (now - period_start).total_seconds() % refill_interval
                refill_remaining_seconds = int(refill_interval - elapsed_in_window)
                refill_time = now + datetime.timedelta(seconds=refill_remaining_seconds)
                five_hour_reset_at = refill_time.isoformat() + "Z"

    free_monthly_used = getattr(cr, "free_monthly_used", 0.0) or 0.0
    used_val = free_monthly_used if (plan and plan.id == "free") else quota.credits_used
    return {
        "plan": plan.name if plan else "free",
        "display_name": plan.display_name if plan else "Free",
        "credits_used": used_val,
        "credits_limit": quota.credits_limit,
        # Backward compatibility aliases
        "requests_used": used_val,
        "requests_limit": quota.credits_limit,
        "percent_used": percent_used,
        "reset_at": quota.reset_at.isoformat() + "Z",
        "days_until_reset": days_until_reset,
        "heavy_calls_available": heavy_calls_available,
        "models_allowed": models_allowed,
        "five_hour_quota_exhausted": five_hour_quota_exhausted,
        "five_hour_reset_at": five_hour_reset_at,
        # Free plan specific
        "free_monthly_remaining": free_monthly_remaining,
        "free_bonus_balance": round(free_bonus_balance, 2),
        "free_bonus_limit": round(bonus_limit, 2),
        "free_bonus_percent": round(free_bonus_percent, 2),
    }


@router.get("/plans", summary="List all available subscription plans")
def get_plans(db: Session = Depends(get_db)):
    from ..exchange_rate import ExchangeRateStore
    usd_to_inr = ExchangeRateStore.get_rate()
    plans = db.query(Plan).order_by(Plan.price_inr.asc()).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "display_name": p.display_name,
            "price_inr": p.price_inr,
            # Backward compatibility alias
            "price_usd_cents": int(p.price_inr * 100 / usd_to_inr), # estimated cents
            "credits_per_month": p.credits_per_month,
            # Backward compatibility alias
            "requests_per_month": p.credits_per_month,
            "allowed_models": p.allowed_models,
            "max_context_k": p.max_context_k,
        }
        for p in plans
    ]


@router.post("/subscribe", summary="Create a Razorpay subscription / payment link")
def subscribe(
    req: SubscribeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user),
):
    plan = db.query(Plan).filter(Plan.id == req.plan_id).first()
    if not plan:
        raise HTTPException(status_code=400, detail=f"Plan {req.plan_id} is invalid.")

    try:
        checkout_url = create_razorpay_link(
            user_id=user.id,
            email=user.email,
            plan_name=plan.name,
            amount_inr=plan.price_inr,
            currency=req.currency or "INR"
        )
        logger.info("subscription_link_created", extra={
            "user_id": user.id,
            "email": user.email,
            "plan_id": plan.id,
            "amount_inr": plan.price_inr,
            "checkout_url": checkout_url
        })
        return {"checkout_url": checkout_url}
    except Exception as exc:
        logger.error("subscribe_error", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Failed to generate subscription link: {str(exc)}")


# ── Webpages (Mock Payment / Checkout) ────────────────────────────────────────

@router.get("/billing/mock-checkout", response_class=HTMLResponse, summary="Serve the premium mock Razorpay checkout page")
def mock_checkout(
    user_id: str,
    plan_id: str,
    db: Session = Depends(get_db),
):
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    server_url = os.environ.get("SERVER_URL", "http://localhost:8000")
    success_url = f"{server_url}/billing/success?user_id={user_id}&plan_id={plan_id}&mock=true"
    
    PLAN_USD_PRICES = {
        "free": 0.0,
        "hobby": 7.0,
        "pro": 25.0,
        "max": 55.0,
        "ultimate": 110.0
    }
    from ..exchange_rate import ExchangeRateStore
    usd_to_inr = ExchangeRateStore.get_rate()
    usd_price = PLAN_USD_PRICES.get(plan_id, 0.0)
    price_inr = int(usd_price * usd_to_inr)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UTIM Billing — Complete Payment</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: hsl(230, 25%, 8%);
            --bg-secondary: hsl(230, 20%, 12%);
            --accent-color: hsl(190, 100%, 50%);
            --accent-glow: hsla(190, 100%, 50%, 0.15);
            --text-main: hsl(210, 20%, 95%);
            --text-muted: hsl(210, 10%, 65%);
            
            --glass-bg: hsla(230, 20%, 12%, 0.6);
            --glass-border: hsla(0, 0%, 100%, 0.08);
            --glass-shadow: 0 8px 32px 0 hsla(0, 0%, 0%, 0.37);
            
            --font-family: 'Outfit', 'Inter', -apple-system, sans-serif;
            --transition-smooth: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        
        body {{
            background-color: var(--bg-primary);
            color: var(--text-main);
            font-family: var(--font-family);
            margin: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
            box-sizing: border-box;
            background-image: 
                radial-gradient(circle at 10% 20%, hsla(220, 100%, 50%, 0.05) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, hsla(190, 100%, 50%, 0.05) 0%, transparent 40%);
        }}
        
        .container {{
            width: 100%;
            max-width: 440px;
            animation: fadeIn 0.6s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        
        .card {{
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            border-radius: 20px;
            padding: 40px;
            text-align: center;
            box-shadow: var(--glass-shadow);
        }}
        
        .logo {{
            font-weight: 700;
            font-size: 1.25rem;
            color: var(--text-main);
            margin-bottom: 30px;
            letter-spacing: -0.01em;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }}
        
        .logo::before {{
            content: '';
            display: inline-block;
            width: 8px;
            height: 8px;
            background-color: var(--accent-color);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--accent-color);
        }}
        
        h2 {{
            font-size: 1.6rem;
            margin: 0 0 8px 0;
            font-weight: 600;
            letter-spacing: -0.02em;
        }}
        
        .plan-badge {{
            display: inline-block;
            background: hsla(190, 100%, 50%, 0.1);
            color: var(--accent-color);
            padding: 6px 16px;
            border-radius: 100px;
            font-weight: 600;
            font-size: 0.85rem;
            margin-bottom: 24px;
            border: 1px solid hsla(190, 100%, 50%, 0.2);
        }}
        
        .price {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 20px;
            letter-spacing: -0.02em;
        }}
        
        .price span {{
            font-size: 1rem;
            color: var(--text-muted);
            font-weight: 400;
        }}
        
        .details {{
            text-align: left;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
            border: 1px solid rgba(255, 255, 255, 0.03);
        }}
        
        .detail-item {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 12px;
            font-size: 0.95rem;
        }}
        
        .detail-item:last-child {{
            margin-bottom: 0;
            padding-top: 12px;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            font-weight: 600;
        }}
        
        .label {{
            color: var(--text-muted);
        }}
        
        .value {{
            color: var(--text-main);
        }}
        
        .pay-btn {{
            display: block;
            width: 100%;
            background: linear-gradient(135deg, hsl(190, 100%, 50%), hsl(220, 100%, 50%));
            color: #fff;
            border: none;
            padding: 16px;
            border-radius: 10px;
            font-weight: 600;
            font-size: 1.05rem;
            cursor: pointer;
            box-shadow: 0 4px 15px var(--accent-glow);
            transition: var(--transition-smooth);
            text-decoration: none;
        }}
        
        .pay-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px hsla(190, 100%, 50%, 0.3);
        }}
        
        .pay-btn:active {{
            transform: translateY(0);
        }}
        
        .cancel-link {{
            display: block;
            margin-top: 16px;
            color: var(--text-muted);
            text-decoration: none;
            font-size: 0.9rem;
            transition: var(--transition-smooth);
        }}
        
        .cancel-link:hover {{
            color: var(--text-main);
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
    </style>
</head>
<body>
    <main class="container">
        <section class="card">
            <div class="logo">UTIM Billing</div>
            <h2>Complete Subscription</h2>
            <div class="plan-badge">{plan.display_name} Plan</div>
            <div class="price">${usd_price:.2f}<span>/month</span></div>
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: -12px; margin-bottom: 24px;">
                ~ ₹{price_inr:,}.00 INR (converted dynamically at ₹{usd_to_inr:.2f}/USD)
            </div>
            
            <div class="details">
                <div class="detail-item">
                    <span class="label">Monthly Quota</span>
                    <span class="value">{plan.credits_per_month:,} credits (${plan.credits_per_month / 1000.0:.2f} value)</span>
                </div>
                <div class="detail-item">
                    <span class="label">Payment Provider</span>
                    <span class="value">Razorpay (Mock)</span>
                </div>
                <div class="detail-item">
                    <span class="label">Total Amount</span>
                    <span class="value">${usd_price:.2f} USD (~₹{price_inr:,}.00 INR)</span>
                </div>
            </div>
            
            <a href="{success_url}" class="pay-btn" id="pay-button">Proceed to Payment</a>
            <a href="#" onclick="window.close(); return false;" class="cancel-link">Cancel</a>
        </section>
    </main>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


@router.get("/billing/success", response_class=HTMLResponse, summary="Serve the premium checkout success redirection landing page")
def success_page(
    user_id: str,
    plan_id: str,
    razorpay_payment_link_id: Optional[str] = Query(None),
    razorpay_payment_link_status: Optional[str] = Query(None),
    razorpay_subscription_id: Optional[str] = Query(None),
    mock: Optional[bool] = Query(False),
    db: Session = Depends(get_db),
):
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify Razorpay status if real
    is_valid = False
    if mock and os.environ.get("UTIM_MOCK_PAYMENTS", "false").lower() == "true":
        is_valid = True
    elif razorpay_payment_link_status == "paid":
        is_valid = True
    elif razorpay_payment_link_id:
        is_valid = verify_payment_link(razorpay_payment_link_id)
    elif razorpay_subscription_id:
        is_valid = verify_subscription(razorpay_subscription_id)

    if not is_valid:
        raise HTTPException(status_code=400, detail="Payment verification failed or payment is pending.")

    logger.info("payment_verified", extra={
        "user_id": user_id,
        "plan_id": plan_id,
        "razorpay_payment_link_id": razorpay_payment_link_id,
        "razorpay_subscription_id": razorpay_subscription_id,
        "mock": mock
    })

    # Activate
    activate_subscription(
        db,
        user_id=user_id,
        plan_id=plan_id,
        razorpay_sub_id=razorpay_subscription_id or razorpay_payment_link_id,
        razorpay_cust_id=f"cust_{user_id[:8]}"
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UTIM — Payment Successful</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: hsl(230, 25%, 8%);
            --bg-secondary: hsl(230, 20%, 12%);
            --success-color: hsl(140, 100%, 45%);
            --success-glow: hsla(140, 100%, 45%, 0.15);
            --text-main: hsl(210, 20%, 95%);
            --text-muted: hsl(210, 10%, 65%);
            
            --glass-bg: hsla(230, 20%, 12%, 0.6);
            --glass-border: hsla(0, 0%, 100%, 0.08);
            --glass-shadow: 0 8px 32px 0 hsla(0, 0%, 0%, 0.37);
            
            --font-family: 'Outfit', 'Inter', -apple-system, sans-serif;
            --transition-smooth: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        
        body {{
            background-color: var(--bg-primary);
            color: var(--text-main);
            font-family: var(--font-family);
            margin: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            background-image: 
                radial-gradient(at 0% 0%, hsla(140, 100%, 45%, 0.03) 0px, transparent 50%),
                radial-gradient(at 100% 100%, hsla(220, 100%, 50%, 0.03) 0px, transparent 50%);
        }}
        
        .container {{
            width: 100%;
            max-width: 480px;
            padding: 20px;
        }}
        
        .card {{
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: 20px;
            box-shadow: var(--glass-shadow);
            padding: 40px;
            text-align: center;
            animation: scaleIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
        }}
        
        .icon {{
            width: 72px;
            height: 72px;
            background: hsla(140, 100%, 45%, 0.1);
            border: 1px solid hsla(140, 100%, 45%, 0.2);
            color: var(--success-color);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 24px;
            font-size: 2rem;
            box-shadow: 0 0 20px var(--success-glow);
        }}
        
        h1 {{
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 12px;
            letter-spacing: -0.02em;
        }}
        
        p {{
            color: var(--text-muted);
            line-height: 1.6;
            margin-bottom: 30px;
            font-size: 1rem;
        }}
        
        .close-btn {{
            display: block;
            width: 100%;
            background: linear-gradient(135deg, hsl(140, 100%, 45%), hsl(160, 100%, 40%));
            color: #fff;
            border: none;
            padding: 16px;
            border-radius: 10px;
            font-weight: 600;
            font-size: 1.05rem;
            cursor: pointer;
            box-shadow: 0 4px 15px var(--success-glow);
            transition: var(--transition-smooth);
            text-decoration: none;
        }}
        
        .close-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px hsla(140, 100%, 45%, 0.3);
        }}
        
        @keyframes scaleIn {{
            from {{ transform: scale(0.9); opacity: 0; }}
            to {{ transform: scale(1); opacity: 1; }}
        }}
    </style>
</head>
<body>
    <main class="container">
        <section class="card">
            <div class="icon">✓</div>
            <h1>Subscription Activated!</h1>
            <p>Thank you for subscribing to the <strong>{plan.display_name}</strong> plan. Your monthly quota of <strong>{plan.credits_per_month:,}</strong> credits (${plan.credits_per_month / 1000.0:.2f} value) is now active.<br><br>You can close this tab and return to the terminal.</p>
            <a href="#" onclick="window.close(); return false;" class="close-btn">Done</a>
        </section>
    </main>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


class ApiSubscribeRequest(BaseModel):
    plan: str
    interval: Optional[str] = "monthly"
    currency: Optional[str] = "INR"


class ApiVerifyRequest(BaseModel):
    razorpay_subscription_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/api/subscription/create")
def api_subscription_create(
    req: ApiSubscribeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user)
):
    plan_name = req.plan.lower().strip()
    if plan_name == "starter":
        db_plan_id = "pro"
    elif plan_name == "professional":
        db_plan_id = "max"
    else:
        db_plan_id = plan_name
        
    plan = db.query(Plan).filter(Plan.id == db_plan_id).first()
    if not plan:
        if db_plan_id == "starter":
            plan = Plan(
                id="starter",
                name="starter",
                display_name="Starter",
                price_inr=2500,
                credits_per_month=18000,
                allowed_models="all",
                max_context_k=256
            )
        elif db_plan_id == "pro":
            plan = Plan(
                id="pro",
                name="pro",
                display_name="Pro",
                price_inr=2500,
                credits_per_month=18000,
                allowed_models="all",
                max_context_k=1024
            )
        elif db_plan_id == "max":
            plan = Plan(
                id="max",
                name="max",
                display_name="Max",
                price_inr=5500,
                credits_per_month=45000,
                allowed_models="all",
                max_context_k=1024
            )
        elif db_plan_id == "ultimate":
            plan = Plan(
                id="ultimate",
                name="ultimate",
                display_name="Ultimate Core",
                price_inr=11000,
                credits_per_month=90000,
                allowed_models="all",
                max_context_k=1024
            )
        elif db_plan_id == "hobby":
            plan = Plan(
                id="hobby",
                name="hobby",
                display_name="Hobby",
                price_inr=700,
                credits_per_month=4000,
                allowed_models="all",
                max_context_k=256
            )
        else:
            raise HTTPException(status_code=400, detail=f"Plan {req.plan} not found and cannot be provisioned.")
        db.add(plan)
        db.commit()
        db.refresh(plan)

    key_id = os.environ.get("RAZORPAY_KEY_ID", "").strip()
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()

    interval = (req.interval or "monthly").lower().strip()
    if interval == "yearly":
        raise HTTPException(
            status_code=400,
            detail="Yearly billing interval is not supported. All subscriptions must be monthly."
        )

    currency = (req.currency or "INR").upper().strip()

    # Fetch user's active referral discounts
    from .referral_routes import get_referrer_discounts
    try:
        discounts = get_referrer_discounts(db, user.id)
    except Exception:
        discounts = {}
    
    discount_pct = min(100.0, discounts.get(db_plan_id, 0.0))

    # If the user has a 100% discount, bypass Razorpay payment entirely
    if discount_pct >= 100.0:
        return {
            "success": True,
            "subscriptionId": f"free_referral_100pct_{db_plan_id}_monthly",
            "keyId": "free"
        }

    if not key_id or key_id == "mock_key_id":
        return {
            "success": True,
            "subscriptionId": f"sub_mock_{db_plan_id}_{interval}_{currency}_{uuid.uuid4().hex[:6]}",
            "keyId": "mock_key_id"
        }

    import requests
    
    # Try to load discounted plan from environment variables or JSON mapping
    env_plan_id = None
    if 0.0 < discount_pct < 100.0:
        # Map to closest step of 2 (2%, 4%, ..., 98%)
        pct_step = int(round(discount_pct / 2) * 2)
        pct_step = max(2, min(98, pct_step))
        
        # Determine variable keys checking aliases
        plan_env_name = db_plan_id.upper()
        if plan_env_name == "PRO":
            plan_env_name = "STARTER"
        elif plan_env_name == "MAX":
            plan_env_name = "PROFESSIONAL"
            
        env_key = f"RAZORPAY_PLAN_{plan_env_name}_{pct_step}"
        env_plan_id = os.environ.get(env_key)
        
        # Fallback check for direct DB plan name
        if not env_plan_id:
            env_key_direct = f"RAZORPAY_PLAN_{db_plan_id.upper()}_{pct_step}"
            env_plan_id = os.environ.get(env_key_direct)
            
        if env_plan_id:
            logger.info(f"Dynamic discounted plan resolved from environment: {env_plan_id} ({env_key})")
        else:
            # Fallback to local JSON mapping file
            import json
            json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "razorpay_discounted_plans.json")
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        plans_map = json.load(f)
                    plan_key = f"{db_plan_id}_{pct_step}"
                    env_plan_id = plans_map.get(plan_key)
                    if env_plan_id:
                        logger.info(f"Dynamic discounted plan resolved from JSON: {env_plan_id} for user {user.id} ({plan_key})")
                except Exception as json_err:
                    logger.error(f"Failed to read discounted plans JSON mapping: {json_err}")

    if not env_plan_id:
        env_plan_id = get_razorpay_plan_id(db_plan_id, interval, currency)

    if not env_plan_id:
        raise HTTPException(
            status_code=400, 
            detail=f"Razorpay Plan ID not configured for {db_plan_id} ({interval}, {currency}). Set RAZORPAY_PLAN_{db_plan_id.upper()}_USD or RAZORPAY_PLAN_{db_plan_id.upper()} in environment."
        )

    url = "https://api.razorpay.com/v1/subscriptions"
    auth_str = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_str}",
        "Content-Type": "application/json"
    }
    payload = {
        "plan_id": env_plan_id,
        "total_count": 1 if interval == "yearly" else 12,
        "quantity": 1,
        "customer_notify": 1,
        "notes": {
            "user_id": user.id,
            "plan_id": db_plan_id,
            "interval": interval,
            "currency": currency
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        res_data = response.json()
        return {
            "success": True,
            "subscriptionId": res_data["id"],
            "keyId": key_id
        }
    except Exception as e:
        status_code = getattr(getattr(e, 'response', None), 'status_code', None)
        body = None
        try:
            body = e.response.json() if hasattr(e, 'response') and e.response is not None else None
        except Exception:
            pass
        logger.error(
            f"razorpay_subscription_create_error plan={db_plan_id} status={status_code} "
            f"body={body} key_prefix={key_id[:8] if key_id else 'MISSING'} err={e}"
        )
        raise HTTPException(status_code=500, detail=f"Failed to create Razorpay subscription: {str(e)}")


@router.post("/api/subscription/verify")
def api_subscription_verify(
    req: ApiVerifyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user)
):
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")

    if req.razorpay_subscription_id.startswith("free_referral_100pct") or req.razorpay_subscription_id.startswith("sub_mock") or not key_id or key_id == "mock_key_id":
        plan_id = "hobby"
        interval = "monthly"
        parts = req.razorpay_subscription_id.split("_")
        # free_referral_100pct_{plan_id}_monthly
        if len(parts) >= 4 and parts[3] in ("hobby", "pro", "max", "ultimate"):
            plan_id = parts[3]
        elif len(parts) >= 3 and parts[2] in ("hobby", "pro", "max", "ultimate"):
            plan_id = parts[2]
        if len(parts) >= 5 and parts[4] in ("monthly", "yearly"):
            interval = parts[4]
        elif len(parts) >= 4 and parts[3] in ("monthly", "yearly"):
            interval = parts[3]
        activate_subscription(db, user_id=user.id, plan_id=plan_id, razorpay_sub_id=req.razorpay_subscription_id, interval=interval)
        # Award referral discount to referrer if applicable
        try:
            from .referral_routes import apply_referral_purchase
            apply_referral_purchase(db, referee_id=user.id, plan_id=plan_id)
        except Exception as _ref_err:
            logger.warning(f"referral_purchase_hook_failed: {_ref_err}")
        return {"success": True}

    import hmac
    import hashlib
    
    msg = f"{req.razorpay_payment_id}|{req.razorpay_subscription_id}"
    generated_sig = hmac.new(
        key_secret.encode('utf-8'),
        msg.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    if generated_sig != req.razorpay_signature:
        logger.warning("razorpay_signature_mismatch", extra={"subscription_id": req.razorpay_subscription_id})
        raise HTTPException(status_code=400, detail="Signature verification failed.")

    import requests
    
    url = f"https://api.razorpay.com/v1/subscriptions/{req.razorpay_subscription_id}"
    auth_str = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    headers = {"Authorization": f"Basic {auth_str}"}
    
    plan_id = "hobby"
    interval = "monthly"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            notes = response.json().get("notes", {})
            plan_id = notes.get("plan_id", "hobby")
            interval = notes.get("interval", "monthly")
    except Exception:
        pass

    activate_subscription(
        db,
        user_id=user.id,
        plan_id=plan_id,
        razorpay_sub_id=req.razorpay_subscription_id,
        razorpay_cust_id=f"cust_{user.id[:8]}",
        interval=interval
    )

    # Award referral discount to referrer if applicable
    try:
        from .referral_routes import apply_referral_purchase
        apply_referral_purchase(db, referee_id=user.id, plan_id=plan_id)
    except Exception as _ref_err:
        logger.warning(f"referral_purchase_hook_failed: {_ref_err}")

    return {"success": True}


class UserPlanUpdateRequest(BaseModel):
    plan: str


@router.get("/api/user-plan")
def get_user_plan(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user)
):
    sub = user.subscription
    plan_name = "free"
    plan_display_name = "Free"
    if sub and sub.status == "active" and sub.plan:
        plan_name = sub.plan.name
        plan_display_name = sub.plan.display_name
    return {
        "plan": plan_name,
        "plan_display_name": plan_display_name,
        "firebase_uid": user.firebase_uid,
        "email": user.email,
        "user_id": user.id,
        "display_name": user.display_name
    }


@router.post("/api/user-plan")
def update_user_plan(
    req: UserPlanUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user)
):
    plan = db.query(Plan).filter(Plan.name == req.plan).first()
    if not plan:
        raise HTTPException(status_code=400, detail=f"Plan {req.plan} not found")
        
    activate_subscription(db, user.id, plan.id)
    return {"success": True, "plan": plan.name}




@router.get("/api/usage", summary="Get usage quota remaining percentage and refresh time")
def get_usage(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user),
):
    from ..db import Credit, UserSubscription, Plan
    import datetime
    
    try:
        sub = user.subscription
        plan = sub.plan if (sub and sub.status == "active") else None
        
        credit = user.credits
        balance = credit.balance if credit else 0.0
        bonus_balance = credit.bonus_balance if (credit and hasattr(credit, "bonus_balance")) else 0.0
        
        max_bonus_limit = get_max_bonus_limit(plan.id if plan else "free")
        if max_bonus_limit > 0.0:
            bonus_quota_percent = (bonus_balance / max_bonus_limit) * 100.0
            bonus_quota_percent = min(100.0, max(0.0, bonus_quota_percent))
        else:
            bonus_quota_percent = 0.0
        
        if not plan or plan.id == "free":
            is_subscribed = False
            plan_name = "Free"
            FREE_MONTHLY_CAP = 3000.0
            FREE_SLOT_CAP = 100.0
            refill_interval = 5 * 3600
            now = datetime.datetime.utcnow()

            credit = db.query(Credit).filter(Credit.user_id == user.id).first()
            balance = credit.balance if credit else 0.0
            bonus_balance = getattr(credit, "bonus_balance", 0.0) or 0.0
            bonus_limit = getattr(credit, "bonus_limit", 0.0) or 0.0
            free_monthly_used = getattr(credit, "free_monthly_used", 0.0) or 0.0

            # Reset free_monthly_used if subscription period rolled over
            if sub:
                period_start = sub.current_period_start or sub.created_at or now
                elapsed_in_window = (now - period_start).total_seconds() % refill_interval
                refill_remaining_seconds = int(refill_interval - elapsed_in_window)
                refills_processed = sub.refills_processed or 0
                # Reset monthly tracker if new billing month started
                period_end = sub.current_period_end or (period_start + datetime.timedelta(days=30))
                if now > period_end and credit:
                    credit.free_monthly_used = 0.0
                    free_monthly_used = 0.0
                    db.commit()
            else:
                refill_remaining_seconds = 0
                refills_processed = 0

            max_refills = 144  # 3000 / 100 * ... (6 per day * 30 days)
            refill_rate = 100.0  # 100 credits per 5h slot
            max_bank_limit = FREE_SLOT_CAP

            # 5-hour refill bar: how full is the current slot balance (0-100)
            percent_remaining = min(100.0, max(0.0, (balance / FREE_SLOT_CAP) * 100.0))
            five_hour_quota_percent = percent_remaining
            quota_bank_percent = 0.0  # free plan has no quota bank

            # Bonus bar: ratio of remaining bonus to original bonus limit
            if max_bonus_limit > 0.0:
                bonus_quota_percent = min(100.0, max(0.0, (bonus_balance / max_bonus_limit) * 100.0))
            else:
                bonus_quota_percent = 0.0

            # Monthly allowance remaining
            free_monthly_remaining = max(0.0, FREE_MONTHLY_CAP - free_monthly_used)
        else:
            is_subscribed = True
            plan_name = plan.display_name
            max_bank_limit = plan.credits_per_month * 2.0
            refill_interval = 5 * 3600
            now = datetime.datetime.utcnow()
            
            period_start = sub.current_period_start or sub.created_at or now
            period_end = sub.current_period_end or (period_start + datetime.timedelta(days=30))
            
            elapsed_in_window = (now - period_start).total_seconds() % refill_interval
            refill_remaining_seconds = int(refill_interval - elapsed_in_window)
            
            cycle_days = (period_end - period_start).days
            is_yearly = cycle_days > 45
            max_refills = 1728 if is_yearly else 144
            refills_processed = sub.refills_processed or 0
            # Always divide by 144.0 per month to get the correct 5h slot rate
            refill_rate = round(plan.credits_per_month / 144.0, 2)
            
            # Calculate 5-hour cycle quota remaining percent
            cycle_allowance = plan.credits_per_month / 144.0
            current_cycle_used = sub.current_cycle_used or 0.0
            five_hour_quota_percent = ((cycle_allowance - current_cycle_used) / cycle_allowance) * 100.0
            five_hour_quota_percent = min(100.0, max(0.0, five_hour_quota_percent))
            
            # Calculate quota bank remaining percent
            quota_bank_percent = (balance / max_bank_limit) * 100.0
            quota_bank_percent = min(100.0, max(0.0, quota_bank_percent))
            percent_remaining = quota_bank_percent
            
        return {
            "is_subscribed": is_subscribed,
            "plan_name": plan_name,
            "balance": round(balance, 2),
            "max_limit": round(max_bank_limit, 2),
            "percent_remaining": round(percent_remaining, 2),
            "refills_in_seconds": refill_remaining_seconds,
            "refills_processed": refills_processed,
            "max_refills": max_refills,
            "refill_rate": refill_rate,
            "five_hour_quota_percent": round(five_hour_quota_percent, 2),
            "quota_bank_percent": round(quota_bank_percent, 2),
            "bonus_balance": round(bonus_balance, 2),
            "bonus_limit": round(max_bonus_limit, 2),
            "bonus_quota_percent": round(bonus_quota_percent, 2),
            # Free plan monthly cap tracking
            "free_monthly_remaining": round(free_monthly_remaining if not is_subscribed else -1.0, 2),
            "free_monthly_cap": 3000.0 if not is_subscribed else -1.0,
        }
    except Exception as e:
        return {
            "is_subscribed": False,
            "plan_name": "Free",
            "balance": 0.0,
            "max_limit": 100.0,
            "percent_remaining": 0.0,
            "refills_in_seconds": 0,
            "refills_processed": 0,
            "max_refills": 144,
            "refill_rate": 100.0,
            "five_hour_quota_percent": 0.0,
            "quota_bank_percent": 0.0,
            "bonus_balance": 0.0,
            "bonus_limit": 20000.0,
            "bonus_quota_percent": 0.0,
            "error": str(e)
        }


