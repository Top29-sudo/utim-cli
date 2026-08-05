"""
UTIM Production Server — Auth Layer
API-key authentication using X-API-Key or Authorization: Bearer headers.
"""
from __future__ import annotations

import re
import socket
import logging
import os
import uuid
import datetime
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .db import User, Credit, UserSubscription, QuotaUsage, get_db

logger = logging.getLogger("utim.auth")

# ── Disposable & Fake Email Domain Blacklist ─────────────────────────────────
DISPOSABLE_DOMAINS = {
    "mailinator.com", "dispostable.com", "10minutemail.com", "tempmail.com",
    "trashmail.com", "fakeinbox.com", "yopmail.com", "getairmail.com",
    "guerrillamail.com", "sharklasers.com", "throwawaymail.com", "temp-mail.org",
    "gmx.com", "test.com", "example.com", "asdf.com", "fake.com", "foo.com",
    "bar.com", "domain.com", "invalid.com", "email.com", "temp.com"
}


def validate_email_address(email: str) -> tuple[bool, str]:
    """Validate email syntax, check against disposable domains, and verify domain DNS resolving."""
    if not email or not isinstance(email, str):
        return False, "Email address is required."

    email = email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        return False, "Invalid email format."

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        return False, "Invalid email address format."

    parts = email.split("@")
    if len(parts) != 2:
        return False, "Invalid email address."

    domain = parts[1]

    # Bypass DNS lookup for internal/synthetic firebase user accounts
    if domain == "firebase.user" or domain.endswith(".firebase.user"):
        return True, ""

    if domain in DISPOSABLE_DOMAINS or any(domain.endswith("." + d) for d in DISPOSABLE_DOMAINS):
        return False, "Disposable or fake email addresses are not allowed. Please use a valid email address."

    try:
        socket.getaddrinfo(domain, 80)
    except socket.gaierror:
        return False, f"Email domain '{domain}' does not exist or cannot be reached. Please check for typos."
    except Exception:
        pass

    return True, ""


# ── Master admin key (set in Railway env vars) ────────────────────────────────
MASTER_KEY = os.environ.get("UTIM_MASTER_KEY", None)

# ── Helpers ───────────────────────────────────────────────────────────────────

def process_user_refills(db: Session, user_id: str) -> None:
    """
    Catch-up and process any pending 5-hour quota refills for the user's active subscription.
    Max refills per 30-day billing cycle = 144.
    """
    import datetime
    import uuid
    from .db import UserSubscription, Credit, Transaction
    
    sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == user_id,
        UserSubscription.status == "active"
    ).first()
    
    now = datetime.datetime.utcnow()
    
    if not sub or not sub.plan:
        return

    if sub.plan_id == "free":
        # Handle monthly cycle end — reset the counter
        if sub.current_period_end and now >= sub.current_period_end:
            sub.refills_processed = 0
            sub.current_period_start = now
            sub.current_period_end = now + datetime.timedelta(days=30)
            db.commit()
            
        refills_used = getattr(sub, 'refills_processed', getattr(sub, 'refills_used', 0)) or 0
        if refills_used >= 144:
            return  # Hit monthly cap of 144 refills (3000 credits max)

        last_refill = sub.last_refill_at or sub.created_at
        elapsed_seconds = (now - last_refill).total_seconds()
        
        # Calculate how many 5-hour intervals have passed since last refill
        INTERVAL_SECONDS = 5 * 3600  # 5 hours
        intervals_passed = int(elapsed_seconds // INTERVAL_SECONDS)
        
        if intervals_passed > 0:
            # Cap intervals to not exceed the 144 monthly limit
            intervals_to_apply = min(intervals_passed, 144 - refills_used)
            
            if intervals_to_apply > 0:
                credit_row = db.query(Credit).filter(Credit.user_id == user_id).first()
                if credit_row:
                    old_bal = credit_row.balance or 0.0
                    # Add $0.50 (20 credits) per interval, capped at $2.50 (100 credits) max balance
                    # If balance is already >= $2.50, balance stays same but refill interval updates
                    amount_to_add = intervals_to_apply * 20.0
                    new_bal = min(100.0, old_bal + amount_to_add)
                    actual_added = new_bal - old_bal
                    
                    credit_row.balance = new_bal
                    sub.refills_processed = refills_used + intervals_to_apply
                    sub.last_refill_at = last_refill + datetime.timedelta(seconds=intervals_to_apply * INTERVAL_SECONDS)
                    
                    if actual_added > 0:
                        tx = Transaction(
                            id=str(uuid.uuid4()),
                            user_id=user_id,
                            kind="refill",
                            amount=actual_added,
                            balance_after=new_bal,
                            description=f"Auto-refill: +{actual_added:.1f} credits ({intervals_to_apply} interval{'s' if intervals_to_apply > 1 else ''})"
                        )
                        db.add(tx)
                    
                    db.commit()
                    logger.info("refill_processed", extra={"user_id": user_id, "intervals": intervals_to_apply, "new_balance": new_bal})
        return
    
    # Calculate how many 5-hour refills should have been processed by now
    cycle_days = (sub.current_period_end - sub.current_period_start).days
    is_yearly = cycle_days > 45
    max_refills = 1728 if is_yearly else 144

    if now >= sub.current_period_end:
        max_due = max_refills
    else:
        elapsed_seconds = (now - sub.current_period_start).total_seconds()
        max_due = min(max_refills, int(elapsed_seconds // (5 * 3600)))
        
    due = max_due - sub.refills_processed
    if due > 0:
        plan = sub.plan
        cycle_allowance = plan.credits_per_month / 144.0
        
        # Unused quota from the first due cycle (which had sub.current_cycle_used accumulated)
        # plus the full allowance of any subsequent due cycles where the user didn't make requests
        current_cycle_used = sub.current_cycle_used or 0.0
        unused_credits = max(0.0, cycle_allowance - current_cycle_used)
        if due > 1:
            unused_credits += cycle_allowance * (due - 1)
            
        # Cap refills to remaining monthly plan credits after direct deductions
        unallocated_deducted = getattr(sub, "unallocated_deducted", 0.0) or 0.0
        remaining_pool = max(0.0, plan.credits_per_month - (sub.refills_processed * cycle_allowance) - unallocated_deducted)
        unused_credits = min(unused_credits, remaining_pool)
        
        credit = db.query(Credit).filter(Credit.user_id == user_id).first()
        if not credit:
            credit = Credit(user_id=user_id, balance=0.0, total_spent=0.0, total_topped_up=0.0)
            db.add(credit)
            db.flush()
            
        max_limit = plan.credits_per_month * 2.0
        old_balance = credit.balance
        new_balance = min(max_limit, credit.balance + unused_credits)
        
        if new_balance > old_balance:
            credit.balance = new_balance
            tx = Transaction(
                id=str(uuid.uuid4()),
                user_id=user_id,
                kind="refill",
                amount=new_balance - old_balance,
                balance_after=new_balance,
                description=f"Refill of {due} cycles ({plan.name.title()} Plan)"
            )
            db.add(tx)
            
        sub.current_cycle_used = 0.0
        sub.refills_processed = max_due
        sub.last_refill_at = now
        db.commit()


def _extract_token(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """Pull the raw key/token from headers."""
    if x_api_key:
        return x_api_key
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
    return None


def get_current_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI Dependency: Extract user from X-API-Key or Authorization: Bearer <key>.
    Raises 401 if missing, invalid, or revoked.
    """
    token = x_api_key
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        logger.warning("auth_missing_header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Pass X-API-Key or Authorization: Bearer <key>.",
        )

    user = db.query(User).filter(
        ((User.api_key == token) | (User.email == token) | (User.id == token)),
        User.is_active == True
    ).first()
    if not user:
        logger.warning("auth_failed", extra={"token_prefix": token[:8]})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key.",
        )

    _bootstrap_welcome_email(db, user)
    process_user_refills(db, user.id)
    return user


def get_optional_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    FastAPI Dependency: Extract user if API key header is present, returns None if unauthenticated.
    """
    token = x_api_key
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        return None

    user = db.query(User).filter(
        ((User.api_key == token) | (User.email == token) | (User.id == token)),
        User.is_active == True
    ).first()
    if user:
        _bootstrap_welcome_email(db, user)
        process_user_refills(db, user.id)
    return user


def get_admin_user(
    token: Optional[str] = Depends(_extract_token),
    db: Session = Depends(get_db),
) -> User:
    """Require the UTIM_MASTER_KEY for admin operations."""
    master_key = os.environ.get("UTIM_MASTER_KEY", None)
    if not master_key:
        raise HTTPException(status_code=500, detail="Master key not configured on server.")
    if token != master_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return None  # admin endpoints don't return a user object


def get_current_firebase_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    token = x_api_key
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            
    if not token:
        raise HTTPException(status_code=401, detail="Authorization token missing.")
        
    # Check if token is a direct UTIM API Key
    user_by_key = db.query(User).filter(User.api_key == token, User.is_active == True).first()
    if user_by_key:
        _bootstrap_welcome_email(db, user_by_key)
        process_user_refills(db, user_by_key.id)
        return user_by_key

    # Verify as Firebase JWT Token
    from .firebase import verify_firebase_token
    try:
        payload = verify_firebase_token(token)
    except ValueError as exc:
        logger.warning(f"firebase_token_auth_failed: {exc}")
        raise HTTPException(status_code=401, detail=str(exc))
        
    email = (payload.email or f"{payload.uid}@firebase.user").strip().lower()

    # Check if email is verified by Firebase (Google OAuth/link), by EmailOTP table, or if user is already provisioned in DB
    from sqlalchemy import func
    from .db import EmailOTP
    has_otp_verified = db.query(EmailOTP).filter(
        func.lower(EmailOTP.email) == email,
        EmailOTP.verified == True
    ).first() is not None

    existing_user = db.query(User).filter(func.lower(User.email) == email).first()

    # OTP-verified users in our DB are considered fully verified.
    # Firebase email_verified is only checked for non-OTP users who have no DB record.
    if not payload.email_verified and not has_otp_verified and not existing_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your email address has not been verified yet. Please verify your email via the 6-digit code we sent you."
        )

    user = existing_user or create_user(db, email=email, display_name=payload.name)
    if existing_user and payload.name and (not existing_user.display_name or existing_user.display_name == email.split("@")[0] or existing_user.display_name == "UTIM Developer"):
        existing_user.display_name = payload.name
        db.commit()
    _bootstrap_welcome_email(db, user)

    if not user.firebase_uid or user.firebase_uid != payload.uid:
        user.firebase_uid = payload.uid
        db.commit()

    process_user_refills(db, user.id)
    return user


def get_optional_firebase_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[User]:
    try:
        return get_current_firebase_user(x_api_key=x_api_key, authorization=authorization, db=db)
    except HTTPException:
        return None


# ── Provisioning ──────────────────────────────────────────────────────────────

def create_user(db: Session, email: str, display_name: str = "") -> User:
    """Create a new user with initial credits and quota subscription. Idempotent by email."""
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        if display_name and (not existing.display_name or existing.display_name == email.split("@")[0] or existing.display_name == "UTIM Developer"):
            existing.display_name = display_name
            db.commit()
        return existing

    is_valid, err_msg = validate_email_address(email)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)

    user = User(
        id=str(uuid.uuid4()),
        email=email,
        display_name=display_name or email.split("@")[0],
        api_key=f"utim-{uuid.uuid4().hex}",
        is_active=True,
    )
    db.add(user)
    db.flush()  # get user.id

    # Create credit row for backward compatibility
    credit = Credit(user_id=user.id, balance=100.0, total_topped_up=0.0)
    db.add(credit)

    # Provision Free plan subscription
    now = datetime.datetime.utcnow()
    end_date = now + datetime.timedelta(days=30)
    sub = UserSubscription(
        user_id=user.id,
        plan_id="free",
        status="active",
        current_period_start=now,
        current_period_end=end_date,
    )
    db.add(sub)

    # Create initial quota usage
    quota = QuotaUsage(
        user_id=user.id,
        period_start=now,
        period_end=end_date,
        credits_used=0.0,
        credits_limit=100,  # Free limit: 100 credits
        reset_at=end_date,
    )
    db.add(quota)

    db.commit()
    db.refresh(user)
    
    _bootstrap_welcome_email(db, user)

    logger.info("user_created", extra={"email": email, "user_id": user.id})
    return user


def _bootstrap_welcome_email(db: Session, user: User) -> None:
    """Ensure user has an EmailTracking row and triggers their welcome email if not already sent.

    Sets welcome_email_sent = True in the main DB session BEFORE spawning the thread
    to prevent race conditions (duplicate emails) from parallel requests.
    """
    from .db import EmailTracking
    tracking = db.query(EmailTracking).filter(EmailTracking.user_id == user.id).first()
    if not tracking:
        tracking = EmailTracking(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name or user.email.split("@")[0],
            welcome_email_sent=False
        )
        db.add(tracking)
        db.commit()

    if not tracking.welcome_email_sent:
        # Atomic lock flag: mark True immediately BEFORE starting the thread so concurrent requests skip sending duplicates
        tracking.welcome_email_sent = True
        db.commit()

        email_to_send = user.email
        display_name_to_send = user.display_name or user.email.split("@")[0]
        user_id_to_send = user.id

        from .email_utils import send_welcome_email
        import threading
        def send_bg():
            from .db import SessionLocal, EmailTracking
            thread_db = SessionLocal()
            try:
                success = send_welcome_email(email_to_send, display_name_to_send)
                if not success:
                    # Reset flag if sending failed so it can retry next session
                    try:
                        thread_tracking = thread_db.query(EmailTracking).filter(EmailTracking.user_id == user_id_to_send).first()
                        if thread_tracking:
                            thread_tracking.welcome_email_sent = False
                            thread_db.commit()
                    except Exception as db_exc:
                        thread_db.rollback()
                        logger.warning(f"Could not reset welcome_email_sent flag: {db_exc}")
            except Exception as e:
                logger.error(f"Error sending welcome email in thread: {e}")
                try:
                    thread_tracking = thread_db.query(EmailTracking).filter(EmailTracking.user_id == user_id_to_send).first()
                    if thread_tracking:
                        thread_tracking.welcome_email_sent = False
                        thread_db.commit()
                except Exception as db_exc:
                    thread_db.rollback()
                    logger.warning(f"Could not reset welcome_email_sent flag on error: {db_exc}")
            finally:
                thread_db.close()
        threading.Thread(target=send_bg, daemon=True).start()
