import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from utim_cli.server.router import app
from utim_cli.server.db import SessionLocal, User, PaymentOrder, init_db

def test_credits_topup_flow():
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == 'topup_test@utim.dev').first()
        if not user:
            user = User(email='topup_test@utim.dev')
            db.add(user)
            db.commit()
            db.refresh(user)

        client = TestClient(app)
        
        with patch('utim_cli.server.firebase.verify_firebase_token') as mock_firebase:
            mock_payload = MagicMock()
            mock_payload.email = 'topup_test@utim.dev'
            mock_payload.name = 'Topup Test'
            mock_payload.uid = 'firebase_topup_123'
            mock_firebase.return_value = mock_payload

            headers = {'Authorization': 'Bearer dummy_token'}

            # 1. Test GET /api/credits
            resp = client.get('/api/credits', headers=headers)
            assert resp.status_code == 200
            assert 'balance' in resp.json()

            # 2. Test POST /api/credits/topup in mock mode
            with patch.dict(os.environ, {'RAZORPAY_KEY_ID': '', 'RAZORPAY_KEY_SECRET': '', 'UTIM_MOCK_PAYMENTS': 'true'}):
                resp_topup = client.post('/api/credits/topup', json={'amount': 10.0}, headers=headers)
                assert resp_topup.status_code == 200
                data = resp_topup.json()
                assert data['success'] is True
                assert data['orderId'].startswith('order_mock')
                order_id = data['orderId']

                # Verify PaymentOrder created in DB
                po = db.query(PaymentOrder).filter(PaymentOrder.order_id == order_id).first()
                assert po is not None
                assert po.amount == 10.0
                assert po.status == 'created'

                # 3. Test POST /api/credits/verify/{chargeId} in mock mode
                resp_verify = client.post(f'/api/credits/verify/{order_id}', json={
                    'razorpay_payment_id': 'pay_mock_123',
                    'razorpay_signature': 'sig_mock_123'
                }, headers=headers)
                assert resp_verify.status_code == 200
                assert resp_verify.json()['success'] is True

                # Check PaymentOrder updated in DB
                db.refresh(po)
                assert po.status == 'completed'
                assert po.razorpay_payment_id == 'pay_mock_123'

                # Check User credit balance increased
                db.refresh(user)
                assert user.credits is not None
                assert user.credits.total_topped_up >= 10000.0
    finally:
        db.close()
