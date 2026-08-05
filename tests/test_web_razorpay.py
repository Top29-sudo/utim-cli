import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from utim_cli.server.router import app
from utim_cli.server.db import SessionLocal, User, init_db

def test_web_subscription_create_and_verify():
    init_db()
    db = SessionLocal()
    try:
        # Create test user
        user = db.query(User).filter(User.email == "web_test@utim.dev").first()
        if not user:
            user = User(email="web_test@utim.dev")
            db.add(user)
            db.commit()
            db.refresh(user)

        client = TestClient(app)
        
        # Mock verify_firebase_token to return the test user email
        with patch("utim_cli.server.firebase.verify_firebase_token") as mock_firebase:
            mock_payload = MagicMock()
            mock_payload.email = "web_test@utim.dev"
            mock_payload.name = "Web Test"
            mock_payload.uid = "firebase_uid_123"
            mock_firebase.return_value = mock_payload

            # Headers containing a dummy token
            headers = {"Authorization": "Bearer dummy_token"}

            # 1. Test create subscription in mock mode
            with patch.dict(os.environ, {"RAZORPAY_KEY_ID": "", "RAZORPAY_KEY_SECRET": ""}):
                resp = client.post("/api/subscription/create", json={"plan": "hobby"}, headers=headers)
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                assert data["subscriptionId"].startswith("sub_mock")
                assert data["keyId"] == "mock_key_id"

            # 2. Test verify subscription in mock mode
            resp_verify = client.post("/api/subscription/verify", json={
                "razorpay_subscription_id": "sub_mock_12345",
                "razorpay_payment_id": "pay_mock_12345",
                "razorpay_signature": "sig_mock_12345"
            }, headers=headers)
            assert resp_verify.status_code == 200
            assert resp_verify.json()["success"] is True

            # 3. Verify in real mode (mocking Razorpay APIs)
            with patch.dict(os.environ, {
                "RAZORPAY_KEY_ID": "rzp_live_key",
                "RAZORPAY_KEY_SECRET": "secret_key",
                "RAZORPAY_PLAN_HOBBY": "plan_hobby_rzp"
            }):
                # Mock requests.post for Razorpay API subscription create
                with patch("requests.post") as mock_post:
                    mock_resp = MagicMock()
                    mock_resp.status_code = 200
                    mock_resp.json.return_value = {
                        "id": "sub_real_123",
                        "status": "created"
                    }
                    mock_post.return_value = mock_resp

                    resp = client.post("/api/subscription/create", json={"plan": "hobby"}, headers=headers)
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["success"] is True
                    assert data["subscriptionId"] == "sub_real_123"
                    assert data["keyId"] == "rzp_live_key"

                # Verify signature match
                # payment_id | subscription_id
                import hmac
                import hashlib
                msg = "pay_real_123|sub_real_123"
                expected_sig = hmac.new(b"secret_key", msg.encode('utf-8'), hashlib.sha256).hexdigest()

                # Mock requests.get for Razorpay subscription detail
                with patch("requests.get") as mock_get:
                    mock_resp_get = MagicMock()
                    mock_resp_get.status_code = 200
                    mock_resp_get.json.return_value = {
                        "id": "sub_real_123",
                        "status": "active",
                        "notes": {"plan_id": "hobby"}
                    }
                    mock_get.return_value = mock_resp_get

                    resp_verify = client.post("/api/subscription/verify", json={
                        "razorpay_subscription_id": "sub_real_123",
                        "razorpay_payment_id": "pay_real_123",
                        "razorpay_signature": expected_sig
                    }, headers=headers)
                    assert resp_verify.status_code == 200
                    assert resp_verify.json()["success"] is True

                    # Check DB subscription is activated
                    db.refresh(user)
                    assert user.subscription is not None
                    assert user.subscription.plan_id == "hobby"
                    assert user.subscription.razorpay_subscription_id == "sub_real_123"

                    # 4. Test GET /api/user-plan
                    resp_plan = client.get("/api/user-plan", headers=headers)
                    assert resp_plan.status_code == 200
                    assert resp_plan.json()["plan"] == "hobby"

                    # 5. Test POST /api/user-plan
                    resp_update_plan = client.post("/api/user-plan", json={"plan": "pro"}, headers=headers)
                    assert resp_update_plan.status_code == 200
                    assert resp_update_plan.json()["plan"] == "pro"
    finally:
        db.close()

