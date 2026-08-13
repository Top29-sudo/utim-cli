"""
Routes: /auth — Firebase login, user provisioning & API key management

Auth flow:
  1. CLI opens browser → Firebase sign-in page
  2. Firebase issues an ID token (RS256 JWT) and redirects to localhost callback
  3. CLI POSTs the ID token to POST /auth/firebase-login
  4. Server verifies the token using Google's public keys (no service account needed)
  5. Server auto-provisions the user (idempotent) and returns UTIM api_key
  6. CLI stores api_key locally and uses it as X-API-Key for all future requests
"""
from __future__ import annotations

import datetime
import logging
import os
import random
import string
import uuid
import threading
import requests
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status, Form, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import Credit, DeviceAuthCode, Transaction, User, get_db
from ..auth import create_user, get_admin_user, get_current_user, get_current_firebase_user
from ..rate_limit import limiter
from ..cli_auth import issue_nonce, is_enforcement_enabled
from ..captcha import verify_captcha, verify_captcha_with_header

router = APIRouter(tags=["auth"])
logger = logging.getLogger("utim.routes.auth")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_user_code() -> str:
    """Generate a human-readable 8-char code like 'DFRG-TYHJ'."""
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(random.choices(chars, k=4))
    part2 = ''.join(random.choices(chars, k=4))
    return f"{part1}-{part2}"


class SendOTPRequest(BaseModel):
    email: str


class VerifyOTPRequest(BaseModel):
    email: str
    otp_code: str
    password: Optional[str] = None
    display_name: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    email: str
    otp_code: str
    new_password: str


class FirebaseLoginRequest(BaseModel):
    id_token: str  # Firebase ID token from the client


class LoginResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    api_key: str
    credits: float
    is_new_user: bool


class RegisterRequest(BaseModel):
    email: str
    display_name: str = ""
    otp_code: Optional[str] = None


class RegisterResponse(BaseModel):
    user_id: str
    email: str
    api_key: str
    credits: float


class TopUpRequest(BaseModel):
    user_id: str
    amount: float
    description: str = "manual top-up"


class DeleteUserRequest(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/auth/firebase-login",
    response_model=LoginResponse,
    summary="Exchange a Firebase ID token for a UTIM API key",
)
@router.post(
    "/api/auth/firebase-login",
    response_model=LoginResponse,
    summary="Exchange a Firebase ID token for a UTIM API key (alias)",
)
@limiter.limit("10/minute")
def firebase_login(request: Request, req: FirebaseLoginRequest, db: Session = Depends(get_db)):
    """
    **Primary login endpoint for the CLI.**

    1. User signs in via Firebase in the browser.
    2. CLI sends the Firebase ID token here.
    3. Server verifies the token with Firebase Admin SDK.
    4. User is auto-provisioned on first login (0 free credits).
    5. Returns the permanent UTIM `api_key` — CLI caches this locally.

    The `api_key` is then used as `X-API-Key` on all subsequent requests.
    """
    from sqlalchemy import func
    from ..firebase import verify_firebase_token

    try:
        payload = verify_firebase_token(req.id_token)
    except ValueError as exc:
        logger.warning("firebase_login_failed", extra={"error": str(exc)})
        raise HTTPException(status_code=401, detail=str(exc))

    if not payload.email:
        raise HTTPException(status_code=400, detail="Firebase token does not contain an email address.")

    email = payload.email.strip().lower()

    # Check if this is a new user before provisioning
    existing = db.query(User).filter(func.lower(User.email) == email).first()
    is_new = existing is None

    user = create_user(db, email=email, display_name=payload.name)
    user.firebase_uid = payload.uid
    db.commit()

    logger.info(
        "firebase_login_success",
        extra={
            "email": payload.email,
            "user_id": user.id,
            "uid": payload.uid,
            "is_new": is_new,
        },
    )

    return LoginResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name or "",
        api_key=user.api_key,
        credits=user.credits.balance if user.credits else 0,
        is_new_user=is_new,
    )


# ── Device Authorization Flow ─────────────────────────────────────────────────

class DeviceRequestResponse(BaseModel):
    device_code: str   # secret — only CLI holds this, sent on every poll
    user_code: str     # short human-readable code shown to the user e.g. "DFRG-TYHJ"
    verify_url: str    # full URL user should open e.g. https://utim.dev/activate?code=DFRG-TYHJ
    expires_in: int    # seconds until the code expires (600 = 10 minutes)
    poll_interval: int # seconds CLI should wait between polls (3)


class DeviceAuthorizeRequest(BaseModel):
    user_code: str   # the short code the user sees on the /activate page
    id_token: str    # Firebase ID token from the web app after user signs in


@router.post(
    "/auth/device/request",
    response_model=DeviceRequestResponse,
    summary="[Device Flow] Request a new device login code",
)
@router.post(
    "/api/auth/device/request",
    response_model=DeviceRequestResponse,
    summary="[Device Flow] Request a new device login code (alias)",
)
@limiter.limit("10/minute")
def device_request(request: Request, db: Session = Depends(get_db)):
    """
    **Step 1 of the Device Authorization Flow.**
    
    CLI calls this to obtain a unique pair of codes:
    - `device_code` — secret token, kept only by the CLI, used for polling
    - `user_code`   — short 8-char code shown to the user (e.g. `DFRG-TYHJ`)
    - `verify_url`  — URL user opens in their browser to authorize the device
    
    Codes expire after 10 minutes.
    """
    import os
    web_url = os.environ.get("UTIM_WEB_URL", "https://utim.dev")

    # Ensure uniqueness of user_code
    for _ in range(10):
        user_code = _generate_user_code()
        existing = db.query(DeviceAuthCode).filter(
            DeviceAuthCode.user_code == user_code,
            DeviceAuthCode.status == "pending",
        ).first()
        if not existing:
            break

    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    code = DeviceAuthCode(
        user_code=user_code,
        expires_at=expires_at,
    )
    db.add(code)
    db.commit()
    db.refresh(code)

    return DeviceRequestResponse(
        device_code=code.device_code,
        user_code=user_code,
        verify_url=f"{web_url}/activate?code={user_code}",
        expires_in=600,
        poll_interval=3,
    )


@router.get(
    "/auth/device/poll",
    summary="[Device Flow] Poll for device authorization status",
)
@router.get(
    "/api/auth/device/poll",
    summary="[Device Flow] Poll for device authorization status (alias)",
)
@limiter.limit("30/minute")
def device_poll(device_code: str, request: Request, db: Session = Depends(get_db)):
    """
    **Step 2 of the Device Authorization Flow.**
    
    CLI polls this endpoint every `poll_interval` seconds with its `device_code`.
    
    Responses:
    - `{"status": "pending"}` — user hasn't authorized yet, keep polling
    - `{"status": "authorized", "api_key": "...", "email": "...", ...}` — success!
    - `{"status": "expired"}` — code expired, CLI should restart flow
    - HTTP 404 — invalid device_code
    """
    code = db.query(DeviceAuthCode).filter(
        DeviceAuthCode.device_code == device_code
    ).first()

    if not code:
        raise HTTPException(status_code=404, detail="Invalid device code.")

    # Check expiry
    if datetime.datetime.utcnow() > code.expires_at:
        code.status = "expired"
        db.commit()
        return {"status": "expired"}

    if code.status == "pending":
        return {"status": "pending"}

    if code.status == "authorized":
        # Return the api_key and burn the code immediately (one-time use)
        user = db.query(User).filter(User.id == code.user_id).first()
        result = {
            "status": "authorized",
            "api_key": code.api_key,
            "email": user.email if user else "",
            "display_name": user.display_name if user else "",
            "user_id": code.user_id,
            "firebase_uid": user.firebase_uid if user else "",
            "credits": user.credits.balance if user and user.credits else 0,
        }
        # Invalidate: delete the row so this device_code can never be reused
        db.delete(code)
        db.commit()
        return result

    return {"status": code.status}


@router.post(
    "/auth/device/authorize",
    summary="[Device Flow] Authorize a pending device code (called by web app after Firebase login)",
)
@router.post(
    "/api/auth/device/authorize",
    summary="[Device Flow] Authorize a pending device code (alias)",
)
@limiter.limit("10/minute")
def device_authorize(request: Request, req: DeviceAuthorizeRequest, db: Session = Depends(get_db)):
    """
    **Step 3 of the Device Authorization Flow.**
    
    The web app (`/activate` page) calls this after the user signs in via Firebase.
    Looks up the pending `user_code`, verifies the Firebase token,
    provisions the user if needed, and marks the code as authorized.
    """
    from ..firebase import verify_firebase_token

    # Verify the Firebase token
    try:
        payload = verify_firebase_token(req.id_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    email = payload.email.strip().lower()

    from sqlalchemy import func
    from ..db import EmailOTP
    has_otp_verified = db.query(EmailOTP).filter(
        func.lower(EmailOTP.email) == email,
        EmailOTP.verified == True
    ).first() is not None

    existing_user = db.query(User).filter(func.lower(User.email) == email).first()

    if not payload.email_verified and not has_otp_verified and not existing_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your email address has not been verified yet. Please verify your email via OTP code before activating your device."
        )

    # Look up the pending device code
    code = db.query(DeviceAuthCode).filter(
        DeviceAuthCode.user_code == req.user_code,
        DeviceAuthCode.status == "pending",
    ).first()

    if not code:
        raise HTTPException(status_code=404, detail="Invalid or already used activation code.")

    if datetime.datetime.utcnow() > code.expires_at:
        code.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="Activation code has expired. Please restart the login flow in your terminal.")

    # Provision or fetch the user
    user = create_user(db, email=email, display_name=payload.name)
    user.firebase_uid = payload.uid

    # Authorize the code
    code.status = "authorized"
    code.api_key = user.api_key
    code.user_id = user.id
    db.commit()

    logger.info("device_authorized", extra={"email": user.email, "user_id": user.id})
    return {"success": True}
@router.post("/auth/send-otp", summary="Send a 6-digit OTP verification code to email")
@router.post("/auth/code/request", summary="Send a 6-digit verification code to email (AdBlocker-safe alias)")
@router.post("/api/auth/send-otp", summary="Send a 6-digit OTP verification code to email (alias)")
@router.post("/api/auth/code/request", summary="Send a 6-digit verification code to email (alias)")
@limiter.limit("5/minute")
def send_otp(request: Request, req: SendOTPRequest, db: Session = Depends(get_db)):
    """Validate email address syntax & deliverability and dispatch a 6-digit OTP email."""
    from ..auth import validate_email_address
    from ..db import EmailOTP
    from ..email_utils import send_otp_email

    email = req.email.strip().lower()
    is_valid, err_msg = validate_email_address(email)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)

    now = datetime.datetime.utcnow()
    # Invalidate any active unverified OTPs for this email
    db.query(EmailOTP).filter(
        EmailOTP.email == email,
        EmailOTP.verified == False
    ).delete(synchronize_session=False)

    # Generate 6-digit random numeric code
    otp_code = f"{random.randint(100000, 999999)}"
    expires_at = now + datetime.timedelta(minutes=10)

    otp_entry = EmailOTP(
        id=str(uuid.uuid4()),
        email=email,
        otp_code=otp_code,
        verified=False,
        expires_at=expires_at,
        created_at=now
    )
    db.add(otp_entry)
    db.commit()

    def send_bg():
        try:
            send_otp_email(email, otp_code)
        except Exception as exc:
            logger.error(f"Failed to send OTP email to {email}: {exc}")

    threading.Thread(target=send_bg, daemon=True).start()

    return {
        "success": True,
        "message": f"Verification code sent to {email}. Code expires in 10 minutes."
    }


@router.post("/auth/verify-otp", summary="Verify a 6-digit OTP code")
@router.post("/auth/code/verify", summary="Verify a 6-digit verification code (AdBlocker-safe alias)")
@router.post("/api/auth/verify-otp", summary="Verify a 6-digit OTP code (alias)")
@router.post("/api/auth/code/verify", summary="Verify a 6-digit verification code (alias)")
@limiter.limit("10/minute")
def verify_otp(request: Request, req: VerifyOTPRequest, db: Session = Depends(get_db)):
    """Verify the 6-digit OTP code sent to the email."""
    from ..db import EmailOTP
    from sqlalchemy import func

    email = req.email.strip().lower()
    otp_code = req.otp_code.strip()
    now = datetime.datetime.utcnow()

    otp_row = db.query(EmailOTP).filter(
        func.lower(EmailOTP.email) == email,
        EmailOTP.otp_code == otp_code,
        EmailOTP.expires_at > now
    ).order_by(EmailOTP.created_at.desc()).first()

    if not otp_row:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code. Please request a new code.")

    if not otp_row.verified:
        otp_row.verified = True
        db.commit()

    # Pre-create or update the user record with display_name right now so it's available immediately
    from ..db import User
    from ..auth import create_user, _bootstrap_welcome_email
    display_name = (req.display_name or '').strip()
    existing_user = db.query(User).filter(func.lower(User.email) == email).first()
    if existing_user:
        if display_name and (not existing_user.display_name or existing_user.display_name in ('', 'UTIM Developer', email.split('@')[0])):
            existing_user.display_name = display_name
            db.commit()
            logger.info(f"Updated display_name for {email} to '{display_name}' during OTP verify")
        provisioned_user = existing_user
    else:
        provisioned_user = create_user(db, email=email, display_name=display_name or email.split('@')[0])

    # Send welcome email — idempotent, fires only once per user (same as Google login path)
    try:
        _bootstrap_welcome_email(db, provisioned_user)
    except Exception as exc:
        logger.warning(f"Failed to send welcome email during OTP verify for {email}: {exc}")

    # If password is provided, auto-provision or sync the password in Firebase Auth
    if req.password and len(req.password.strip()) >= 6:
        api_key = os.environ.get("FIREBASE_API_KEY", "AIzaSyAV-L3jY6dS3wXMMNGnYnPTX3IuqBFqK4E")
        try:
            id_token = None
            signup_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
            resp_signup = requests.post(signup_url, json={"email": email, "password": req.password.strip(), "returnSecureToken": True}, timeout=10)
            if resp_signup.ok:
                id_token = resp_signup.json().get("idToken")
                logger.info(f"Firebase account created for {email} during OTP verify")
            else:
                err_msg = resp_signup.json().get("error", {}).get("message", "")
                if "EMAIL_EXISTS" in err_msg:
                    logger.info(f"Email {email} already exists in Firebase Auth during OTP verify, signing in to get token...")
                    # Sign in to get a fresh id token
                    signin_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
                    resp_signin = requests.post(signin_url, json={"email": email, "password": req.password.strip(), "returnSecureToken": True}, timeout=10)
                    if resp_signin.ok:
                        id_token = resp_signin.json().get("idToken")

            # Mark emailVerified=True using the id token so subsequent logins pass the email_verified JWT check
            if id_token:
                update_url = f"https://identitytoolkit.googleapis.com/v1/accounts:update?key={api_key}"
                resp_update = requests.post(update_url, json={"idToken": id_token, "emailVerified": True, "returnSecureToken": True}, timeout=10)
                if resp_update.ok:
                    logger.info(f"Firebase emailVerified=True set for {email}")
                else:
                    logger.warning(f"Failed to set emailVerified for {email}: {resp_update.text}")
        except Exception as exc:
            logger.warning(f"Failed to auto-provision Firebase password during OTP verify for {email}: {exc}")

    return {
        "success": True,
        "message": "Email address verified successfully!"
    }


@router.post("/auth/send-reset-otp", summary="Send a 6-digit OTP code for password reset")
@router.post("/auth/code/reset-request", summary="Send a 6-digit code for password reset (AdBlocker-safe alias)")
@router.post("/api/auth/send-reset-otp", summary="Send a 6-digit OTP code for password reset (alias)")
@router.post("/api/auth/code/reset-request", summary="Send a 6-digit code for password reset (alias)")
@limiter.limit("5/minute")
def send_reset_otp(
    request: Request,
    req: SendOTPRequest,
    db: Session = Depends(get_db),
    x_captcha_token: str | None = Header(default=None, alias="X-Captcha-Token"),
    captcha_ok: bool = Depends(verify_captcha_with_header),
):
    """Check if email exists and dispatch a 6-digit password reset OTP email."""
    from ..auth import validate_email_address
    from ..db import EmailOTP, User
    from ..email_utils import send_otp_email

    from sqlalchemy import func

    email = req.email.strip().lower()
    is_valid, err_msg = validate_email_address(email)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)

    # Verify user exists in database
    existing_user = db.query(User).filter(func.lower(User.email) == email).first()
    if not existing_user:
        raise HTTPException(status_code=404, detail="No account found with this email address. Please check for typos or register.")

    now = datetime.datetime.utcnow()
    # Invalidate any active unverified OTPs for this email
    db.query(EmailOTP).filter(
        func.lower(EmailOTP.email) == email,
        EmailOTP.verified == False
    ).delete(synchronize_session=False)

    otp_code = f"{random.randint(100000, 999999)}"
    expires_at = now + datetime.timedelta(minutes=10)

    otp_entry = EmailOTP(
        id=str(uuid.uuid4()),
        email=email,
        otp_code=otp_code,
        verified=False,
        expires_at=expires_at,
        created_at=now
    )
    db.add(otp_entry)
    db.commit()

    def send_bg():
        try:
            send_otp_email(email, otp_code)
        except Exception as exc:
            logger.error(f"Failed to send password reset OTP to {email}: {exc}")

    threading.Thread(target=send_bg, daemon=True).start()

    return {
        "success": True,
        "message": f"Password reset verification code sent to {email}. Code expires in 10 minutes."
    }


@router.post("/auth/reset-password", summary="Reset password using verified 6-digit OTP code")
@router.post("/auth/code/reset-confirm", summary="Reset password using verified code (AdBlocker-safe alias)")
@router.post("/api/auth/reset-password", summary="Reset password using verified 6-digit OTP code (alias)")
@router.post("/api/auth/code/reset-confirm", summary="Reset password using verified code (alias)")
@limiter.limit("5/minute")
def reset_password(
    request: Request,
    req: ResetPasswordRequest,
    db: Session = Depends(get_db),
    x_captcha_token: str | None = Header(default=None, alias="X-Captcha-Token"),
    captcha_ok: bool = Depends(verify_captcha_with_header),
):
    """Verify 6-digit OTP code and update the user's password in Firebase Auth."""
    from ..db import EmailOTP, User
    from sqlalchemy import func

    email = req.email.strip().lower()
    otp_code = req.otp_code.strip()
    new_password = req.new_password.strip()

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters long.")

    # Check user exists
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found with this email address.")

    now = datetime.datetime.utcnow()
    otp_row = db.query(EmailOTP).filter(
        func.lower(EmailOTP.email) == email,
        EmailOTP.otp_code == otp_code,
        EmailOTP.expires_at > now
    ).order_by(EmailOTP.created_at.desc()).first()

    if not otp_row:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code. Please request a new code.")

    otp_row.verified = True
    db.commit()

    # Update or provision password in Firebase Auth via Identity Toolkit REST API
    api_key = os.environ.get("FIREBASE_API_KEY", "AIzaSyAV-L3jY6dS3wXMMNGnYnPTX3IuqBFqK4E")

    try:
        # Step 1: Try creating / provisioning the user in Firebase Auth if not already created
        signup_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
        resp_signup = requests.post(signup_url, json={"email": email, "password": new_password, "returnSecureToken": True}, timeout=10)

        if resp_signup.ok:
            logger.info(f"Successfully provisioned/set password in Firebase Auth for {email}")
            return {
                "success": True,
                "message": "Your passphrase has been updated successfully! You can now log in with your new passphrase."
            }

        # Step 2: If EMAIL_EXISTS (account already present in Firebase Auth), send OOB password reset email to user's inbox
        oob_url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
        resp_oob = requests.post(oob_url, json={"requestType": "PASSWORD_RESET", "email": email}, timeout=10)

        if resp_oob.ok:
            logger.info(f"Dispatched Firebase Auth password reset email for {email}")
            return {
                "success": True,
                "message": f"Password reset instructions have been dispatched to {email}. Check your inbox!"
            }
        else:
            err_msg = resp_oob.json().get("error", {}).get("message", "Failed to dispatch password reset email.")
            logger.error(f"Failed sendOobCode for {email}: {err_msg}")
            raise HTTPException(status_code=400, detail=f"Firebase Auth error: {err_msg}")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error during reset_password for {email}: {exc}")
        raise HTTPException(status_code=500, detail=f"An error occurred while resetting password: {exc}")


@router.post(
    "/auth/register",
    response_model=RegisterResponse,
    summary="[Dev] Register directly with email (no Firebase)",
)
@limiter.limit("10/minute")
def register(
    request: Request,
    req: RegisterRequest,
    db: Session = Depends(get_db),
    x_captcha_token: str | None = Header(default=None, alias="X-Captcha-Token"),
    captcha_ok: bool = Depends(verify_captcha_with_header),
):
    """
    Direct email registration — useful for local development / testing.
    In production, prefer `POST /auth/firebase-login`.

    Gated by CAPTCHA (set UTIM_CAPTCHA_PROVIDER=off in dev to disable). Tokens
    may be passed either as form field `captcha_token` or as header
    `X-Captcha-Token`.
    """
    from ..auth import validate_email_address
    is_valid, err_msg = validate_email_address(req.email)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)

    user = create_user(db, req.email, req.display_name)
    logger.info("register", extra={"email": req.email, "user_id": user.id})
    return RegisterResponse(
        user_id=user.id,
        email=user.email,
        api_key=user.api_key,
        credits=user.credits.balance if user.credits else 0,
    )


# ── CLI signature challenge endpoint ──────────────────────────────────────────

class ChallengeResponse(BaseModel):
    nonce: str
    expires_at: int            # epoch seconds
    ttl_seconds: int
    enforcement_enabled: bool  # True if signed requests are required on protected paths
    server_version: str        # server build version (for client-side compatibility check)


@router.get(
    "/auth/cli-challenge",
    response_model=ChallengeResponse,
    summary="Fetch a short-lived nonce for signing CLI requests",
)
@limiter.limit("30/minute")
def cli_challenge(
    request: Request,
    x_utim_install_id: str | None = Header(default=None, alias="X-UTIM-Install-ID"),
):
    """Returns a single-use nonce the CLI uses to build its X-UTIM-CLI-Signature.

    The CLI should call this once per request (or cache for a few seconds when
    bursting). The nonce binds to (install_id, ip) so a leaked nonce cannot be
    replayed by a different caller.
    """
    install_id = (x_utim_install_id or "").strip()[:64]
    ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else ""))
    nonce, expires_at = issue_nonce(install_id=install_id, ip=ip)

    # Best-effort server version (no hard dependency on _version.py being on sys.path)
    server_version = "unknown"
    try:
        from utim_cli._version import VERSION  # type: ignore
        server_version = VERSION
    except Exception:
        pass

    return ChallengeResponse(
        nonce=nonce,
        expires_at=expires_at,
        ttl_seconds=max(1, expires_at - int(__import__("time").time())),
        enforcement_enabled=is_enforcement_enabled(),
        server_version=server_version,
    )


@router.get("/auth/me", summary="Get the authenticated user's profile")
def me(user: User = Depends(get_current_user)):
    return {
        "user_id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "api_key": user.api_key,
        "credits": user.credits.balance if user.credits else 0,
        "total_spent": user.credits.total_spent if user.credits else 0,
        "total_topped_up": user.credits.total_topped_up if user.credits else 0,
        "created_at": user.created_at.isoformat(),
    }


@router.post("/auth/topup", summary="[Admin] Add credits to a user account")
@limiter.limit("5/minute")
def topup(
    request: Request,
    req: TopUpRequest,
    db: Session = Depends(get_db),
    _: None = Depends(get_admin_user),
):
    """Requires `X-API-Key: <UTIM_MASTER_KEY>`. Records an immutable transaction."""
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.credits:
        user.credits = Credit(user_id=user.id)
        db.add(user.credits)

    user.credits.balance += req.amount
    user.credits.total_topped_up += req.amount
    new_balance = user.credits.balance

    tx = Transaction(
        id=str(uuid.uuid4()),
        user_id=user.id,
        kind="topup",
        amount=req.amount,
        balance_after=new_balance,
        description=req.description,
    )
    db.add(tx)

    # Grant free spin for every $5 (5000 credits) manual top-up
    spins_to_add = int((req.amount / 1000.0) // 5.0)
    if spins_to_add > 0:
        from .rewards_routes import _get_or_create_spin_cycle
        cycle = _get_or_create_spin_cycle(db, user.id)
        cycle.spins_granted += spins_to_add

    db.commit()

    logger.info(
        "topup",
        extra={"user_id": user.id, "amount": req.amount, "new_balance": new_balance},
    )
    return {"status": "ok", "new_balance": new_balance}


@router.post("/auth/delete-user", summary="[Admin] Delete a user and all their data")
def delete_user(
    req: DeleteUserRequest,
    db: Session = Depends(get_db),
    _: None = Depends(get_admin_user),
):
    from ..db import User, EmailTracking
    
    if not req.user_id and not req.email:
        raise HTTPException(status_code=400, detail="Either user_id or email must be provided.")
        
    query = db.query(User)
    if req.user_id:
        query = query.filter(User.id == req.user_id)
    else:
        query = query.filter(User.email == req.email)
        
    user_obj = query.first()
    if not user_obj:
        raise HTTPException(status_code=404, detail="User not found")
        
    user_email = user_obj.email
    user_id = user_obj.id

    # Delete EmailTracking manually
    db.query(EmailTracking).filter(EmailTracking.user_id == user_id).delete()
    
    # Delete User (cascades to all other database references)
    db.delete(user_obj)
    db.commit()
    
    logger.info("user_deleted", extra={"email": user_email, "user_id": user_id})
    return {"success": True, "detail": f"User {user_email} and all related data deleted successfully."}


@router.delete("/api/auth/delete-me", summary="Allow an authenticated user to permanently delete their own account")
def delete_me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user)
):
    from ..db import EmailTracking
    
    user_email = user.email
    user_id = user.id

    # Delete EmailTracking manually
    db.query(EmailTracking).filter(EmailTracking.user_id == user_id).delete()
    
    # Delete User (cascades to all other database references)
    db.delete(user)
    db.commit()
    
    logger.info("user_self_deleted", extra={"email": user_email, "user_id": user_id})
    return {"success": True, "detail": "Your account and all associated data have been permanently deleted."}


class LastFolderRequest(BaseModel):
    folder_path: str


@router.get("/api/auth/last-folder", summary="Get last used project folder path")
def get_last_folder(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return {"folder_path": user.last_project_folder}


@router.post("/api/auth/last-folder", summary="Set last used project folder path")
def set_last_folder(
    req: LastFolderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    user.last_project_folder = req.folder_path
    db.commit()
    return {"success": True, "folder_path": user.last_project_folder}
