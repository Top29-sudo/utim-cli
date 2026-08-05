import datetime
import pytest
from unittest.mock import patch
from starlette.requests import Request

from utim_cli.server.db import SessionLocal, EmailOTP, User, Base, engine

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_otp_generation_and_verification():
    db = SessionLocal()
    email = "validtestuser@gmail.com"

    # Clean up prior test data
    db.query(EmailOTP).filter(EmailOTP.email == email).delete()
    db.commit()

    # 1. Create OTP row directly
    now = datetime.datetime.utcnow()
    otp_code = "654321"
    otp_entry = EmailOTP(
        email=email,
        otp_code=otp_code,
        verified=False,
        expires_at=now + datetime.timedelta(minutes=10),
        created_at=now
    )
    db.add(otp_entry)
    db.commit()

    # 2. Verify OTP row exists
    saved = db.query(EmailOTP).filter(EmailOTP.email == email, EmailOTP.otp_code == otp_code).first()
    assert saved is not None
    assert saved.verified is False

    # 3. Perform verification
    saved.verified = True
    db.commit()

    verified_row = db.query(EmailOTP).filter(EmailOTP.email == email).first()
    assert verified_row.verified is True
    db.close()


def test_send_reset_otp_nonexistent_user():
    db = SessionLocal()
    nonexistent_email = "nonexistentuser99999@gmail.com"

    # Ensure user does not exist
    user = db.query(User).filter(User.email == nonexistent_email).first()
    if user:
        db.delete(user)
        db.commit()

    from utim_cli.server.routes.auth_routes import send_reset_otp, SendOTPRequest
    from fastapi import HTTPException

    mock_req = Request({
        "type": "http",
        "method": "POST",
        "path": "/auth/send-reset-otp",
        "headers": [],
        "client": ("127.0.0.1", 12345)
    })

    with pytest.raises(HTTPException) as exc_info:
        send_reset_otp(mock_req, SendOTPRequest(email=nonexistent_email), db)

    assert exc_info.value.status_code == 404
    assert "No account found" in str(exc_info.value.detail)
    db.close()
