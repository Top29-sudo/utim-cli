import datetime
import pytest
from unittest import mock
from fastapi import HTTPException

from utim_cli.server.db import SessionLocal, User, Credit, UserSubscription, Plan, init_db, QuotaUsage
from utim_cli.server.routes.completion_routes import (
    generate_3d_task_proxy,
    upload_3d_file_proxy,
    check_3d_task_proxy,
    Tripo3DRequest,
)

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
            display_name="Starter Node",
            price_inr=2500,
            credits_per_month=18000,
            allowed_models="all",
            max_context_k=1024
        )
        db.add(pro_plan)
        
    # Ensure free plan exists
    free_plan = db.query(Plan).filter(Plan.id == "free").first()
    if not free_plan:
        free_plan = Plan(
            id="free",
            name="free",
            display_name="Free Node",
            price_inr=0,
            credits_per_month=1000,
            allowed_models="free",
            max_context_k=128
        )
        db.add(free_plan)
        
    db.commit()
    db.close()
    yield


def test_free_user_blocked_from_3d_endpoints():
    db = SessionLocal()
    
    # Setup Free User
    user = db.query(User).filter(User.email == "free_tester@utim.dev").first()
    if user:
        db.query(Credit).filter(Credit.user_id == user.id).delete()
        db.query(UserSubscription).filter(UserSubscription.user_id == user.id).delete()
        db.delete(user)
        db.commit()
        
    user = User(
        id="free-tester-uid",
        email="free_tester@utim.dev",
        firebase_uid="uid-free-tester",
        display_name="Free Tester"
    )
    db.add(user)
    db.commit()
    
    sub = UserSubscription(
        user_id=user.id,
        plan_id="free",
        status="active",
        current_period_start=datetime.datetime.utcnow(),
        current_period_end=datetime.datetime.utcnow() + datetime.timedelta(days=30),
        refills_processed=0,
        current_cycle_used=0.0,
        unallocated_deducted=0.0,
    )
    db.add(sub)
    db.commit()
    
    # Try calling POST /3d/generations
    req = Tripo3DRequest(
        type="text_to_model",
        prompt="A stylized sword"
    )
    mock_request = mock.Mock()
    mock_request.headers = {}
    
    with pytest.raises(HTTPException) as exc_info:
        generate_3d_task_proxy(mock_request, req, db, user)
    assert exc_info.value.status_code == 403
    assert "Blender & 3D Tools are only available on the Starter plan" in exc_info.value.detail
    
    # Try calling POST /3d/upload
    mock_file = mock.Mock()
    with pytest.raises(HTTPException) as exc_info:
        upload_3d_file_proxy(mock_request, mock_file, db, user)
    assert exc_info.value.status_code == 403
    assert "Blender & 3D Tools are only available on the Starter plan" in exc_info.value.detail

    # Try calling GET /3d/generations/{task_id}
    with pytest.raises(HTTPException) as exc_info:
        check_3d_task_proxy("task-123", mock_request, db, user)
    assert exc_info.value.status_code == 403
    assert "Blender & 3D Tools are only available on the Starter plan" in exc_info.value.detail

    db.close()


@mock.patch("requests.post")
@mock.patch("utim_cli.server.routes.completion_routes.is_promo_active")
def test_starter_user_promo_billing(mock_promo_active, mock_post):
    db = SessionLocal()
    
    # Setup Paid User on Starter plan (pro)
    user = db.query(User).filter(User.email == "starter_tester@utim.dev").first()
    if user:
        db.query(Credit).filter(Credit.user_id == user.id).delete()
        db.query(UserSubscription).filter(UserSubscription.user_id == user.id).delete()
        db.query(QuotaUsage).filter(QuotaUsage.user_id == user.id).delete()
        db.delete(user)
        db.commit()
        
    user = User(
        id="starter-tester-uid",
        email="starter_tester@utim.dev",
        firebase_uid="uid-starter-tester",
        display_name="Starter Tester"
    )
    db.add(user)
    db.commit()
    
    credit = Credit(user_id=user.id, balance=1000.0, bonus_balance=0.0, total_spent=0.0, total_topped_up=0.0)
    db.add(credit)
    
    sub = UserSubscription(
        user_id=user.id,
        plan_id="pro",
        status="active",
        current_period_start=datetime.datetime.utcnow(),
        current_period_end=datetime.datetime.utcnow() + datetime.timedelta(days=30),
        refills_processed=0,
        current_cycle_used=0.0,
        unallocated_deducted=0.0,
    )
    db.add(sub)
    
    quota = QuotaUsage(
        user_id=user.id,
        period_start=datetime.datetime.utcnow(),
        period_end=datetime.datetime.utcnow() + datetime.timedelta(days=30),
        credits_used=0.0,
        credits_limit=18000.0,
        reset_at=datetime.datetime.utcnow() + datetime.timedelta(days=30),
    )
    db.add(quota)
    db.commit()
    
    # Mock Tripo OpenAPI response
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "code": 0,
        "message": "success",
        "data": {
            "task_id": "tripo-task-888"
        }
    }
    
    req = Tripo3DRequest(
        type="image_to_model",
        image_url="https://example.com/sword.png"
    )
    
    mock_request = mock.Mock()
    mock_request.headers = {}
    
    # 1. TEST DURING PROMO PERIOD (is_promo_active = True) -> Expected 20% discount on 500 = 400 credits cost
    mock_promo_active.return_value = True
    with mock.patch.dict("os.environ", {"TRIPO_API_KEY": "fake-key"}):
        resp = generate_3d_task_proxy(mock_request, req, db, user)
            
    db.refresh(sub)
    # Expected: unallocated_deducted has 400.0 deducted (500.0 * 0.8)
    assert resp["data"]["task_id"] == "tripo-task-888"
    assert sub.unallocated_deducted == 360.0
    
    # 2. TEST AFTER PROMO PERIOD (is_promo_active = False) -> Expected normal price (450 credits)
    sub.unallocated_deducted = 0.0
    db.add(sub)
    db.commit()
    
    mock_promo_active.return_value = False
    with mock.patch.dict("os.environ", {"TRIPO_API_KEY": "fake-key"}):
        resp = generate_3d_task_proxy(mock_request, req, db, user)
            
    db.refresh(sub)
    # Expected: unallocated_deducted has full 450.0 deducted
    assert sub.unallocated_deducted == 450.0
    
    db.close()


@mock.patch("requests.post")
@mock.patch("requests.get")
@mock.patch("utim_cli.client_utils.proxy_openrouter_request")
def test_client_side_tool_fallbacks(mock_proxy_req, mock_get, mock_post):
    from utim_cli.tools import analyze_image, web_search, query_codebase
    from utim_cli.config import config
    
    # 1. Mock /quota endpoint returning free plan
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "plan": {
            "id": "free",
            "name": "free"
        }
    }
    
    # Define a helper function to mock config.get dynamically
    original_get = config.get
    def mock_get_func(key, default=None):
        mock_values = {
            "api_key": "fake-key",
            "subagent_model_analyze_image": "gpt-4",
            "subagent_model_web_search": "gpt-4",
        }
        if key in mock_values:
            return mock_values[key]
        return original_get(key, default)

    with mock.patch.object(config, "get", side_effect=mock_get_func):
        with mock.patch("utim_cli.client_utils.get_server_url", return_value="http://127.0.0.1:8000"):
            # Analyze Image: call with free plan.
            # It should fall back to non-agentic local Pillow‑based analysis (which expects an image, so it raises File Not Found),
            # and it should NEVER call OpenRouter / API completions proxy.
            result = analyze_image("nonexistent.png", "describe this")
            assert "Error: Image file 'nonexistent.png' not found." in result
            assert mock_proxy_req.call_count == 0

            # Web Search: call with free plan.
            # It should bypass OpenRouter LLM synthesis call and immediately go to search execution.
            web_search("find latest news about python")
            assert mock_proxy_req.call_count == 0
            
            # Query Codebase: call with free plan.
            # It should bypass LLM fast synthesis model and return raw matching segments in [Non-Agent Codebase Mode]
            # We stub matching FTS results using a mock or simple FTS mock
            # Mock the database helper inside query_codebase
            with mock.patch("sqlite3.connect") as mock_conn:
                mock_cur = mock_conn.return_value.cursor.return_value
                mock_cur.fetchall.return_value = [("file1.py", "print('hello')")]
                result = query_codebase("search python print")
                assert "[Non-Agent Codebase Mode]" in result
                assert "file1.py" in result
                assert mock_proxy_req.call_count == 0
