import os
from fastapi.testclient import TestClient
from utim_cli.server.router import app
from utim_cli.server.db import SessionLocal, User, PaymentOrder, init_db, Credit
from unittest.mock import patch, MagicMock

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

        resp_topup = client.post('/api/credits/topup', json={'amount': 10.0}, headers=headers)
        order_id = resp_topup.json()['orderId']

        # Let's catch the exception by invoking the route logic directly or checking testclient response
        print("Verifying order:", order_id)
        resp_verify = client.post(f'/api/credits/verify/{order_id}', json={
            'razorpay_payment_id': 'pay_mock_123',
            'razorpay_signature': 'sig_mock_123'
        }, headers=headers)
        print("Response status:", resp_verify.status_code)
        print("Response text:", resp_verify.text)
finally:
    db.close()
