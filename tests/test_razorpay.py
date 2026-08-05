import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from utim_cli.server.router import app
from utim_cli.server.db import SessionLocal, User, init_db

def test_razorpay_subscription_creation_and_verification():
    # Setup test DB
    init_db()
    db = SessionLocal()
    try:
        # Create test user
        user = db.query(User).filter(User.email == "razorpay_test@utim.dev").first()
        if not user:
            user = User(email="razorpay_test@utim.dev")
            db.add(user)
            db.commit()
            db.refresh(user)

        client = TestClient(app)
        headers = {"X-API-Key": user.api_key}

        # Mock Razorpay environment variables
        with patch.dict(os.environ, {
            "RAZORPAY_KEY_ID": "rzp_live_123",
            "RAZORPAY_KEY_SECRET": "secret_123",
            "RAZORPAY_PLAN_HOBBY": "plan_hobby_rzp"
        }):
            # Mock requests.post to simulate Razorpay Subscription API response
            with patch("requests.post") as mock_post:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "id": "sub_12345",
                    "short_url": "https://rzp.io/i/sub_12345",
                    "status": "created"
                }
                mock_post.return_value = mock_resp

                resp = client.post("/subscribe", json={"plan_id": "hobby"}, headers=headers)
                assert resp.status_code == 200
                assert resp.json()["checkout_url"] == "https://rzp.io/i/sub_12345"

                # Verify payload was correct
                args, kwargs = mock_post.call_args
                url = args[0]
                assert "subscriptions" in url
                payload = kwargs["json"]
                assert payload["plan_id"] == "plan_hobby_rzp"
                assert payload["notes"]["user_id"] == user.id

            # Verify subscription validation endpoint
            with patch("requests.get") as mock_get:
                mock_resp_get = MagicMock()
                mock_resp_get.status_code = 200
                mock_resp_get.json.return_value = {
                    "id": "sub_12345",
                    "status": "active"
                }
                mock_get.return_value = mock_resp_get

                success_url = f"/billing/success?user_id={user.id}&plan_id=hobby&razorpay_subscription_id=sub_12345"
                resp_success = client.get(success_url)
                assert resp_success.status_code == 200

                # Verify that it activated subscription in db
                db.refresh(user)
                assert user.subscription is not None
                assert user.subscription.plan_id == "hobby"
                assert user.subscription.razorpay_subscription_id == "sub_12345"
    finally:
        db.close()
