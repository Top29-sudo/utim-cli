import datetime
import pytest
from unittest import mock
from fastapi import HTTPException

from utim_cli.server.db import SessionLocal, User, Credit, UserSubscription, Plan, Base, engine, init_db, QuotaUsage
from utim_cli.server.routes.completion_routes import (
    deduct_credits_unallocated_first,
    generate_3d_task_proxy,
    Tripo3DRequest,
)
from utim_cli.server.auth import process_user_refills

@pytest.fixture(autouse=True)
def setup_db():
    init_db(silent=False)
    db = SessionLocal()
    # Ensure pro plan exists
    pro_plan = db.query(Plan).filter(Plan.id == "pro").first()
    if not pro_plan:
        pro_plan = Plan(
            id="pro",
            name="pro",
            display_name="Pro Node",
            price_inr=2500,
            credits_per_month=18000,
            allowed_models="all",
            max_context_k=1024
        )
        db.add(pro_plan)
        db.commit()
    db.close()
    yield


def test_deduct_credits_unallocated_first():
    db = SessionLocal()

    # 1. Setup User
    user = db.query(User).filter(User.email == "billing_tester@utim.dev").first()
    if user:
        db.query(Credit).filter(Credit.user_id == user.id).delete()
        db.query(UserSubscription).filter(UserSubscription.user_id == user.id).delete()
        db.query(QuotaUsage).filter(QuotaUsage.user_id == user.id).delete()
        db.delete(user)
        db.commit()

    user = User(
        id="tester-uid-123",
        email="billing_tester@utim.dev",
        firebase_uid="uid-tester-123",
        display_name="Billing Tester"
    )
    db.add(user)
    db.commit()

    # Setup Credit record
    credit = Credit(user_id=user.id, balance=100.0, bonus_balance=200.0, total_spent=0.0, total_topped_up=0.0)
    db.add(credit)

    # Setup Subscription (18,000 monthly allowance)
    start_time = datetime.datetime.utcnow()
    sub = UserSubscription(
        user_id=user.id,
        plan_id="pro",
        status="active",
        current_period_start=start_time,
        current_period_end=start_time + datetime.timedelta(days=30),
        refills_processed=0,
        current_cycle_used=0.0,
        unallocated_deducted=0.0,
    )
    db.add(sub)

    # Setup QuotaUsage record
    quota = QuotaUsage(
        user_id=user.id,
        period_start=start_time,
        period_end=start_time + datetime.timedelta(days=30),
        credits_used=0.0,
        credits_limit=18000.0,
        reset_at=start_time + datetime.timedelta(days=30),
    )
    db.add(quota)
    db.commit()

    # --- TEST 1: Deduct prioritizing unallocated pool first ---
    # Cost = 750 credits.
    # Expected: unallocated_deducted = 750, current_cycle_used = 0, credit.balance = 100, quota.credits_used = 750
    charged_bonus = deduct_credits_unallocated_first(db, user, 750.0, pref_quota="regular")
    db.refresh(sub)
    db.refresh(credit)
    db.refresh(quota)

    assert charged_bonus == 0.0
    assert sub.unallocated_deducted == 750.0
    assert sub.current_cycle_used == 0.0
    assert credit.balance == 100.0
    assert credit.bonus_balance == 200.0
    assert quota.credits_used == 750.0

    # --- TEST 2: Deduct prioritizing bonus balance first ---
    # Cost = 150 credits, pref_quota="bonus"
    # Expected: bonus_balance = 50, unallocated_deducted = 750, quota.credits_used = 750 + 0 = 750 (since bonus doesn't count towards regular used)
    charged_bonus = deduct_credits_unallocated_first(db, user, 150.0, pref_quota="bonus")
    db.refresh(sub)
    db.refresh(credit)
    db.refresh(quota)

    assert charged_bonus == 150.0
    assert credit.bonus_balance == 50.0
    assert sub.unallocated_deducted == 750.0
    assert quota.credits_used == 750.0

    db.close()


def test_process_user_refills_capping():
    db = SessionLocal()

    # 1. Setup User
    user = db.query(User).filter(User.email == "refill_tester@utim.dev").first()
    if user:
        db.query(Credit).filter(Credit.user_id == user.id).delete()
        db.query(UserSubscription).filter(UserSubscription.user_id == user.id).delete()
        db.query(QuotaUsage).filter(QuotaUsage.user_id == user.id).delete()
        db.delete(user)
        db.commit()

    user = User(
        id="tester-uid-456",
        email="refill_tester@utim.dev",
        firebase_uid="uid-tester-456",
        display_name="Refill Tester"
    )
    db.add(user)
    db.commit()

    # Setup Credit record
    credit = Credit(user_id=user.id, balance=0.0, bonus_balance=0.0, total_spent=0.0, total_topped_up=0.0)
    db.add(credit)

    # Setup Subscription (18,000 monthly allowance -> cycle allowance = 125 credits)
    # Direct deduct 17,800 credits from unallocated pool.
    # Remaining monthly limit available for refills = 18,000 - 17,800 = 200 credits.
    start_time = datetime.datetime.utcnow() - datetime.timedelta(hours=25)  # 5 cycles due
    sub = UserSubscription(
        user_id=user.id,
        plan_id="pro",
        status="active",
        current_period_start=start_time,
        current_period_end=start_time + datetime.timedelta(days=30),
        refills_processed=0,
        current_cycle_used=0.0,
        unallocated_deducted=17800.0,
    )
    db.add(sub)
    db.commit()

    # Run catch-up refills
    process_user_refills(db, user.id)
    db.refresh(credit)
    db.refresh(sub)

    # Total due was 5 cycles = 5 * 125 = 625 credits.
    # But capped at remaining pool = 18000 - 0 - 17800 = 200 credits.
    # Verify exactly 200 credits were added to credit.balance.
    assert credit.balance == 200.0
    assert sub.refills_processed == 5

    db.close()


@mock.patch("requests.post")
def test_tripo_3d_generation_proxy_billing(mock_post):
    db = SessionLocal()

    # Setup User
    user = db.query(User).filter(User.email == "tripo_tester@utim.dev").first()
    if user:
        db.query(Credit).filter(Credit.user_id == user.id).delete()
        db.query(UserSubscription).filter(UserSubscription.user_id == user.id).delete()
        db.query(QuotaUsage).filter(QuotaUsage.user_id == user.id).delete()
        db.delete(user)
        db.commit()

    user = User(
        id="tester-uid-789",
        email="tripo_tester@utim.dev",
        firebase_uid="uid-tester-789",
        display_name="Tripo Tester"
    )
    db.add(user)
    db.commit()

    credit = Credit(user_id=user.id, balance=100.0, bonus_balance=0.0, total_spent=0.0, total_topped_up=0.0)
    db.add(credit)

    start_time = datetime.datetime.utcnow()
    sub = UserSubscription(
        user_id=user.id,
        plan_id="pro",
        status="active",
        current_period_start=start_time,
        current_period_end=start_time + datetime.timedelta(days=30),
        refills_processed=0,
        current_cycle_used=0.0,
        unallocated_deducted=0.0,
    )
    db.add(sub)

    quota = QuotaUsage(
        user_id=user.id,
        period_start=start_time,
        period_end=start_time + datetime.timedelta(days=30),
        credits_used=0.0,
        credits_limit=18000.0,
        reset_at=start_time + datetime.timedelta(days=30),
    )
    db.add(quota)
    db.commit()

    # Mock Tripo API Response
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "code": 0,
        "message": "success",
        "data": {
            "task_id": "tripo-task-999"
        }
    }

    # Build request for image_to_model (500 credits cost)
    req = Tripo3DRequest(
        type="image_to_model",
        image_url="https://example.com/source.png"
    )

    # Mock environment variable and execute proxy
    with mock.patch("utim_cli.server.routes.completion_routes.is_promo_active", return_value=False):
        with mock.patch.dict("os.environ", {"TRIPO_API_KEY": "fake-tripo-key"}):
            mock_request = mock.Mock()
            mock_request.headers = {}
            resp = generate_3d_task_proxy(mock_request, req, db, user)

    db.refresh(sub)
    db.refresh(quota)

    assert resp["data"]["task_id"] == "tripo-task-999"
    assert sub.unallocated_deducted == 450.0
    assert quota.credits_used == 450.0
    
    db.close()


@mock.patch("requests.post")
@mock.patch("requests.get")
def test_generate_3d_model_tool(mock_get, mock_post):
    from utim_cli.tools import generate_3d_model
    import tempfile
    import os
    import shutil
    
    # Mock upload call response
    mock_post.side_effect = [
        # Response 1: upload
        mock.Mock(
            status_code=200,
            json=lambda: {"code": 0, "message": "success", "data": {"file_token": "token-xyz"}}
        ),
        # Response 2: submit generation task
        mock.Mock(
            status_code=200,
            json=lambda: {"code": 0, "message": "success", "data": {"task_id": "task-xyz-123"}}
        )
    ]
    
    # Mock status check and download response
    mock_get.side_effect = [
        # Response 1: status check
        mock.Mock(
            status_code=200,
            json=lambda: {
                "code": 0,
                "message": "success",
                "data": {
                    "status": "success",
                    "result": {
                        "model": "https://example.com/test-model.glb"
                    }
                }
            }
        ),

        # Response 2: glb file download
        mock.Mock(status_code=200, content=b"fake-glb-data")
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.png")
        with open(input_path, "wb") as f:
            f.write(b"fake-image")
        with mock.patch("utim_cli.tools.is_user_starter_or_higher", return_value=True):
            with mock.patch("utim_cli.config.config", {"api_key": "fake-user-api-key"}):
                with mock.patch.dict("os.environ", {"TRIPO_API_KEY": "fake-tripo-key"}):
                    if os.path.exists(".utim_tmp/blender_assets"):
                        try: shutil.rmtree(".utim_tmp/blender_assets")
                        except Exception: pass
                    result = generate_3d_model(
                        type="image_to_model",
                        image_path=input_path,
                        name="output"
                    )
                    assert "Success: 3D model successfully generated" in result
                    assert os.path.isdir(".utim_tmp/blender_assets")
                    assert os.path.isfile(".utim_tmp/blender_assets/output.glb")
                    with open(".utim_tmp/blender_assets/output.glb", "rb") as f:
                        assert f.read() == b"fake-glb-data"
                    try: shutil.rmtree(".utim_tmp/blender_assets")
                    except Exception: pass
