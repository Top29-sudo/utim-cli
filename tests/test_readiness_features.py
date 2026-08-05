import os
os.environ["UTIM_MASTER_KEY"] = "test-master-key"
os.environ["UTIM_MOCK_PAYMENTS"] = "true"
import pytest
from unittest.mock import patch
from utim_cli.tools import validate_syntax, write_file, edit_file, run_command, _DRY_RUN
import utim_cli.tools as _t
from utim_cli.orchestrator import Orchestrator
from rich.console import Console

def test_syntax_validation(tmp_path):
    # Test valid Python
    valid_py = "def hello():\n    return 'world'"
    assert validate_syntax("dummy.py", valid_py) is None

    # Test invalid Python
    invalid_py = "def hello(\n    return 'world'"
    err = validate_syntax("dummy.py", invalid_py)
    assert err is not None
    assert "Syntax Error" in err

    # Test valid JSON
    valid_json = '{"a": 1, "b": "hello"}'
    assert validate_syntax("dummy.json", valid_json) is None

    # Test invalid JSON
    invalid_json = '{"a": 1, "b": "hello"'
    err2 = validate_syntax("dummy.json", invalid_json)
    assert err2 is not None
    assert "JSON Syntax Error" in err2

def test_dry_run_write_and_edit(tmp_path):
    filepath = str(tmp_path / "test_dry.py")
    
    # Enable dry run
    _t._DRY_RUN = True
    try:
        # Test writing
        valid_py = "def add(a, b):\n    return a + b\n"
        res = write_file(filepath, valid_py)
        assert "[Dry Run]" in res
        assert not os.path.exists(filepath)

        # Test writing invalid code in dry run
        invalid_py = "def add(a, b\n"
        res = write_file(filepath, invalid_py)
        assert "Pre-Commit Validation Failed" in res

        # Create real file to test edit_file dry-run
        _t._DRY_RUN = False
        write_file(filepath, valid_py)
        assert os.path.exists(filepath)

        # Edit in dry run
        _t._DRY_RUN = True
        res = edit_file(filepath, "return a + b", "return a - b")
        assert "[Dry Run]" in res
        with open(filepath, "r") as f:
            assert "return a + b" in f.read()  # Unchanged!

        # Edit invalid in dry run
        res = edit_file(filepath, "return a + b", "return a +")
        assert "Pre-Commit Validation Failed" in res
    finally:
        _t._DRY_RUN = False

def test_dry_run_command():
    _t._DRY_RUN = True
    try:
        res = run_command("echo 'hello world'")
        assert "[Dry Run]" in res
        assert "Simulated execution" in res
    finally:
        _t._DRY_RUN = False

def test_automated_test_detection(tmp_path):
    import shutil
    # Create a dummy test runner setup
    dummy_dir = tmp_path / "dummy_project"
    dummy_dir.mkdir()
    
    # Change cwd to dummy_dir to test detection
    old_cwd = os.getcwd()
    os.chdir(dummy_dir)
    try:
        c = Console()
        orch = Orchestrator(c)
        
        # Before setup, should return None (not found)
        assert orch._detect_and_run_tests() is None

        # Setup dummy pytest
        (dummy_dir / "tests").mkdir()
        # Since no pytest is configured to fail, it should pass/None
        assert orch._detect_and_run_tests() is None
    finally:
        os.chdir(old_cwd)

def test_cli_commands(tmp_path):
    from typer.testing import CliRunner
    from utim_cli.utim import app
    
    runner = CliRunner()
    
    # Test version — must include both version number and 'U Think I Make' tagline
    res = runner.invoke(app, ["--version"])
    assert res.exit_code == 0
    assert "UTIM CLI" in res.stdout or "U Think I Make" in res.stdout
    assert "U Think I Make" in res.stdout, (
        f"--version should include tagline 'U Think I Make'. Got: {res.stdout!r}"
    )
    
    # Test doctor
    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 0
    assert "Diagnostics Complete" in res.stdout
    
    # Test init and reset
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        res = runner.invoke(app, ["init"])
        assert res.exit_code == 0
        assert "Workspace initialized successfully" in res.stdout
        assert os.path.exists(".utim")
        
        # Test reset
        res = runner.invoke(app, ["reset"], input="y\n")
        assert res.exit_code == 0
        assert "cleared successfully" in res.stdout
        assert not os.path.exists(".utim")

        # Test logout (already logged out)
        res = runner.invoke(app, ["logout"])
        assert res.exit_code == 0
        assert "logged out" in res.stdout.lower()

        # Test login (mocked auth.login)
        from unittest.mock import patch
        with patch("utim_cli.auth.login") as mock_login:
            res = runner.invoke(app, ["login"])
            assert res.exit_code == 0
            assert mock_login.called
    finally:
        os.chdir(old_cwd)

def test_redact_text():
    """Verify redact_text covers API keys, bearer tokens, emails, keywords, cwd and env var values."""
    from utim_cli.logger import redact_text
    import os

    # API key patterns
    assert "[REDACTED_API_KEY]" in redact_text("key: sk-abc123defgh456ijkl789mnop")
    assert "[REDACTED_API_KEY]" in redact_text("use sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxx for openrouter")

    # Bearer token
    assert "[REDACTED_TOKEN]" in redact_text("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload")

    # Email address
    assert "[REDACTED_EMAIL]" in redact_text("contact: developer@example.com")

    # Sensitive keyword
    assert "[REDACTED]" in redact_text("my girlfriend said hello")

    # Working directory is redacted
    cwd = os.getcwd()
    result = redact_text(f"Working Directory: {cwd}")
    assert cwd not in result
    assert "[WORKSPACE_DIR]" in result

    # Clean text remains unchanged (no false positives)
    plain = "Hello, I fixed a bug in utils.py"
    result = redact_text(plain)
    assert "Hello" in result

def test_report_bundle_no_unicode_error(tmp_path):
    """Verify create_report_bundle runs without UnicodeEncodeError on Windows and returns a zip."""
    import zipfile
    from utim_cli.report import create_report_bundle

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        bundle_path = create_report_bundle()
        assert os.path.exists(bundle_path)
        assert bundle_path.endswith(".zip")
        with zipfile.ZipFile(bundle_path, "r") as z:
            names = z.namelist()
            assert "support_report.txt" in names
            content = z.read("support_report.txt").decode("utf-8")
            assert "UTIM SUPPORT REPORT" in content
            assert "DIAGNOSTICS" in content
            # Working directory must be redacted in the bundle
            assert str(tmp_path) not in content
            # Content must be pure ASCII (safe on any Windows code page)
            content.encode("ascii")  # raises UnicodeEncodeError if non-ASCII present
    finally:
        os.chdir(old_cwd)


def test_server_quota_and_gating():
    from fastapi.testclient import TestClient
    from utim_cli.server.router import app
    from utim_cli.server.db import Plan, User, QuotaUsage, init_db, SessionLocal
    from utim_cli.server.auth import create_user
    import datetime

    init_db()
    db = SessionLocal()
    try:
        # Clean up any existing test user to ensure test isolation
        db.query(User).filter(User.email == "test_pytest@utim.dev").delete()
        db.commit()

        plans = db.query(Plan).all()
        assert len(plans) >= 7  # free, hobby, pro, team, enterprise, max, ultimate
        
        user = create_user(db, "test_pytest@utim.dev", "Pytest User")
        assert user.subscription is not None
        
        client = TestClient(app)
        headers = {"X-API-Key": user.api_key}
        
        # Verify /plans
        resp = client.get("/plans")
        assert resp.status_code == 200
        
        # Verify /quota
        resp = client.get("/quota", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["plan"] == "free"
        
        # Verify model gating on FREE plan BEFORE upgrade: premium models must be blocked (403)
        resp = client.post("/completions", json={
            "messages": [{"role": "user", "content": "hi"}],
            "model_id": "anthropic/claude-opus-4.6"
        }, headers=headers)
        assert resp.status_code == 403, f"Expected 403 on Free plan for premium model, got {resp.status_code}"

        # Verify /subscribe
        resp = client.post("/subscribe", json={"plan_id": "hobby"}, headers=headers)
        assert resp.status_code == 200
        assert "checkout_url" in resp.json()

        # Verify mock success activation
        success_url = f"/billing/success?user_id={user.id}&plan_id=hobby&mock=true"
        resp = client.get(success_url)
        assert resp.status_code == 200

        # After upgrading to Hobby, all models are allowed (no server-side block)
        resp = client.get("/quota", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["plan"] == "hobby"

        # Test reflection billing bypass:
        # 1. Exhaust monthly quota on purpose
        quota = db.query(QuotaUsage).filter(QuotaUsage.user_id == user.id).first()
        quota.credits_used = quota.credits_limit + 10.0
        from utim_cli.server.db import Credit
        credit = db.query(Credit).filter(Credit.user_id == user.id).first()
        if credit:
            credit.bonus_balance = 0.0
        db.commit()
        
        # 2. A normal completions request must be blocked with 429
        resp = client.post("/completions", json={
            "messages": [{"role": "user", "content": "hi"}],
            "model_id": "google/gemini-3.1-pro-preview"
        }, headers=headers)
        assert resp.status_code == 429, f"Expected 429 for normal request after quota exhaust, got {resp.status_code}"
        
        # 3. A reflection request (is_reflection=True) must bypass 429 (should proceed to LLM and return 200 OK stream or 503 if no keys configured)
        resp = client.post("/completions", json={
            "messages": [{"role": "user", "content": "hi"}],
            "model_id": "google/gemini-3.1-pro-preview",
            "is_reflection": True
        }, headers=headers)
        # Bypasses 429 monthly quota check, hits _get_client
        assert resp.status_code != 429, f"Expected request to bypass 429 monthly quota block, got status code {resp.status_code}"
    finally:
        db.close()


def test_yearly_and_degradation_bonus():
    from fastapi.testclient import TestClient
    from utim_cli.server.router import app
    from utim_cli.server.db import User, Credit, init_db, SessionLocal
    from utim_cli.server.auth import create_user
    from utim_cli.server.routes.quota_routes import activate_subscription
    
    init_db()
    db = SessionLocal()
    try:
        # Clean up existing test user
        db.query(User).filter(User.email == "test_bonus@utim.dev").delete()
        db.commit()
        
        user = create_user(db, "test_bonus@utim.dev", "Test Bonus User")
        client = TestClient(app)
        headers = {"X-API-Key": user.api_key}
        
        # 1. Test Yearly calculation
        # Upgrade user to yearly Hobby plan
        activate_subscription(db, user_id=user.id, plan_id="hobby", interval="yearly")
        
        # Check /api/usage
        resp = client.get("/api/usage", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["max_refills"] == 1728
        # 4000 credits per month divided by 144 should be 27.78
        assert data["refill_rate"] == 27.78
        
        # 2. Upgrade to Pro plan
        activate_subscription(db, user_id=user.id, plan_id="pro")
        credit = db.query(Credit).filter(Credit.user_id == user.id).first()
        assert credit is not None
        # Manually set Pro plan credits to $90 (90,000 credits) simulating accumulated quota
        credit.balance = 90000.0
        # Reset bonus balance and limit to 0 so we only test the degradation bonus conversion
        credit.bonus_balance = 0.0
        credit.bonus_limit = 0.0
        db.commit()
        
        # 3. Degrade to Hobby plan
        activate_subscription(db, user_id=user.id, plan_id="hobby")
        
        # Verify credits: bank capped at $7 (7000 credits) and the rest ($83 / 83000 credits) is halved to 41500 credits in bonus_balance
        db.refresh(credit)
        assert credit.balance == 7000.0
        assert credit.bonus_balance == 41500.0
        assert credit.bonus_limit == 41500.0
        
        # Verify /api/usage returns bonus quota
        resp = client.get("/api/usage", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["bonus_balance"] == 41500.0
        assert data["bonus_quota_percent"] == 83.0

        # 4. Upgrade back to Pro plan after some time/use
        activate_subscription(db, user_id=user.id, plan_id="pro")
        db.refresh(credit)
        
        # They should NOT receive the lost quota back (balance shouldn't jump back to 90,000 or have the lost 41,500 added back)
        # Their balance should remain capped/adjusted based on their current status (e.g. 7,000)
        assert credit.balance == 7000.0
        # The bonus quota must remain stagnant/unchanged (still exactly 41,500.0)
        assert credit.bonus_balance == 41500.0
        assert credit.bonus_limit == 41500.0
    finally:
        db.query(User).filter(User.email == "test_bonus@utim.dev").delete()
        db.commit()
        db.close()


def test_subscription_renewal_no_bonus():
    from utim_cli.server.db import User, Credit, UsedEmailBonus, init_db, SessionLocal
    from utim_cli.server.auth import create_user
    from utim_cli.server.routes.quota_routes import activate_subscription
    
    init_db()
    db = SessionLocal()
    try:
        # Clean up existing test user and email bonus records
        db.query(User).filter(User.email == "test_renewal@utim.dev").delete()
        db.query(UsedEmailBonus).filter(UsedEmailBonus.email == "test_renewal@utim.dev").delete()
        db.commit()
        
        user = create_user(db, "test_renewal@utim.dev", "Test Renewal User")
        credit = db.query(Credit).filter(Credit.user_id == user.id).first()
        
        # 1. First purchase of Hobby plan -> awards 500 bonus credits
        activate_subscription(db, user_id=user.id, plan_id="hobby")
        db.refresh(credit)
        assert credit.bonus_balance == 500.0
        assert credit.bonus_limit == 500.0
        
        # 2. Second purchase/renewal of the SAME Hobby plan -> must NOT award any additional bonus credits!
        activate_subscription(db, user_id=user.id, plan_id="hobby")
        db.refresh(credit)
        # Bonus balance and limit must remain exactly 500.0
        assert credit.bonus_balance == 500.0
        assert credit.bonus_limit == 500.0
        
    finally:
        db.query(User).filter(User.email == "test_renewal@utim.dev").delete()
        db.query(UsedEmailBonus).filter(UsedEmailBonus.email == "test_renewal@utim.dev").delete()
        db.commit()
        db.close()


def test_plan_based_bonus_credits():
    from utim_cli.server.db import User, Credit, UsedEmailBonus, init_db, SessionLocal
    from utim_cli.server.auth import create_user
    from utim_cli.server.routes.quota_routes import activate_subscription
    
    init_db()
    db = SessionLocal()
    try:
        db.query(User).filter(User.email == "test_plan_based@utim.dev").delete()
        db.query(UsedEmailBonus).filter(UsedEmailBonus.email == "test_plan_based@utim.dev").delete()
        db.commit()
        
        user = create_user(db, "test_plan_based@utim.dev", "Test Plan Based User")
        credit = db.query(Credit).filter(Credit.user_id == user.id).first()
        
        # 1. Purchase Hobby -> awards 500 bonus
        activate_subscription(db, user_id=user.id, plan_id="hobby")
        db.refresh(credit)
        assert credit.bonus_balance == 500.0
        
        # 2. Purchase Hobby again -> awards nothing
        activate_subscription(db, user_id=user.id, plan_id="hobby")
        db.refresh(credit)
        assert credit.bonus_balance == 500.0
        
        # 3. Upgrade to Max -> awards 5000 bonus
        activate_subscription(db, user_id=user.id, plan_id="max")
        db.refresh(credit)
        assert credit.bonus_balance == 5500.0  # 500 + 5000
        
        # 4. Purchase Max again -> awards nothing
        activate_subscription(db, user_id=user.id, plan_id="max")
        db.refresh(credit)
        assert credit.bonus_balance == 5500.0
        
        # 5. Downgrade/switch back to Hobby -> awards nothing (since Hobby was already purchased/received bonus)
        activate_subscription(db, user_id=user.id, plan_id="hobby")
        db.refresh(credit)
        assert credit.bonus_balance == 5500.0
        
    finally:
        db.query(User).filter(User.email == "test_plan_based@utim.dev").delete()
        db.query(UsedEmailBonus).filter(UsedEmailBonus.email == "test_plan_based@utim.dev").delete()
        db.commit()
        db.close()



def test_delete_recreate_abuse_prevention():
    from utim_cli.server.db import User, Credit, UsedEmailBonus, init_db, SessionLocal
    from utim_cli.server.auth import create_user
    from utim_cli.server.routes.quota_routes import activate_subscription
    
    init_db()
    db = SessionLocal()
    try:
        # Clean up existing test user and email bonus records
        db.query(User).filter(User.email == "abuse_test@utim.dev").delete()
        db.query(UsedEmailBonus).filter(UsedEmailBonus.email == "abuse_test@utim.dev").delete()
        db.commit()
        
        # 1. Create user and subscribe for the first time -> grants bonus
        user = create_user(db, "abuse_test@utim.dev", "Abuse Test User")
        credit = db.query(Credit).filter(Credit.user_id == user.id).first()
        
        activate_subscription(db, user_id=user.id, plan_id="hobby")
        db.refresh(credit)
        assert credit.bonus_balance == 500.0
        
        # 2. Simulate User Deleting their Account (cascades delete on user/credits/transactions)
        db.delete(user)
        db.commit()
        
        # Verify user is completely wiped from main tables
        assert db.query(User).filter(User.email == "abuse_test@utim.dev").first() is None
        assert db.query(Credit).filter(Credit.user_id == user.id).first() is None
        
        # 3. Create a NEW user with the SAME email address
        new_user = create_user(db, "abuse_test@utim.dev", "New Abuse Test User")
        new_credit = db.query(Credit).filter(Credit.user_id == new_user.id).first()
        
        # 4. Subscribe the new user to Hobby -> must NOT award any bonus credits
        activate_subscription(db, user_id=new_user.id, plan_id="hobby")
        db.refresh(new_credit)
        
        # Bonus balance must be 0.0
        assert new_credit.bonus_balance == 0.0
        
    finally:
        db.query(User).filter(User.email == "abuse_test@utim.dev").delete()
        db.query(UsedEmailBonus).filter(UsedEmailBonus.email == "abuse_test@utim.dev").delete()
        db.commit()
        db.close()


def test_admin_delete_user():
    from fastapi.testclient import TestClient
    from utim_cli.server.router import app
    from utim_cli.server.db import User, Credit, EmailTracking, init_db, SessionLocal
    from utim_cli.server.auth import create_user, MASTER_KEY
    
    init_db()
    db = SessionLocal()
    try:
        # Clean up existing test user
        db.query(User).filter(User.email == "test_delete@utim.dev").delete()
        db.commit()
        
        user = create_user(db, "test_delete@utim.dev", "Test Delete User")
        client = TestClient(app)
        
        # 1. Try to delete without master key
        resp = client.post("/auth/delete-user", json={"email": "test_delete@utim.dev"})
        assert resp.status_code == 403
        
        # 2. Try to delete with invalid master key
        resp = client.post("/auth/delete-user", json={"email": "test_delete@utim.dev"}, headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 403
        
        # 3. Delete user with valid master key
        if not MASTER_KEY:
            pytest.skip("UTIM_MASTER_KEY not set")
        headers = {"X-API-Key": MASTER_KEY}
        resp = client.post("/auth/delete-user", json={"email": "test_delete@utim.dev"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        
        # Verify user and related tables are gone
        db.close()
        db = SessionLocal()
        deleted_user = db.query(User).filter(User.email == "test_delete@utim.dev").first()
        assert deleted_user is None
        
        deleted_credit = db.query(Credit).filter(Credit.user_id == user.id).first()
        assert deleted_credit is None
        
        deleted_tracking = db.query(EmailTracking).filter(EmailTracking.user_id == user.id).first()
        assert deleted_tracking is None
    finally:
        db.query(User).filter(User.email == "test_delete@utim.dev").delete()
        db.commit()
        db.close()


@patch("utim_cli.server.firebase.verify_firebase_token")
def test_self_delete_user(mock_verify):
    from fastapi.testclient import TestClient
    from utim_cli.server.router import app
    from utim_cli.server.db import User, Credit, EmailTracking, init_db, SessionLocal
    from utim_cli.server.auth import create_user
    from utim_cli.server.firebase import FirebaseTokenPayload
    
    init_db()
    db = SessionLocal()
    try:
        # Clean up existing test user
        db.query(User).filter(User.email == "test_self_delete@utim.dev").delete()
        db.commit()
        
        user = create_user(db, "test_self_delete@utim.dev", "Self Delete User")
        client = TestClient(app)
        
        # 1. Call delete-me without token
        resp = client.delete("/api/auth/delete-me")
        assert resp.status_code == 401
        
        # 2. Call delete-me with mocked Firebase token
        mock_verify.return_value = FirebaseTokenPayload(
            uid="mock-self-delete-uid",
            email="test_self_delete@utim.dev",
            name="Self Delete User",
            email_verified=True
        )
        
        resp = client.delete("/api/auth/delete-me", headers={"Authorization": "Bearer mock-token"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        
        # Verify user is deleted
        db.close()
        db = SessionLocal()
        deleted_user = db.query(User).filter(User.email == "test_self_delete@utim.dev").first()
        assert deleted_user is None
    finally:
        db.query(User).filter(User.email == "test_self_delete@utim.dev").delete()
        db.commit()
        db.close()


def test_custom_provider_disconnect():
    from utim_cli.config import config
    
    # Save original custom models to restore them after the test
    original_models = config.custom_models
    try:
        config.custom_models = []
        
        # Add models from Provider A
        config.add_custom_model({
            "model_id": "a-1",
            "provider_name": "ProviderA",
            "base_url": "https://api.provider-a.com/v1",
            "api_key": "key-a",
            "context_window": 128000
        })
        config.add_custom_model({
            "model_id": "a-2",
            "provider_name": "ProviderA",
            "base_url": "https://api.provider-a.com/v1",
            "api_key": "key-a",
            "context_window": 128000
        })
        
        # Add models from Provider B
        config.add_custom_model({
            "model_id": "b-1",
            "provider_name": "ProviderB",
            "base_url": "https://api.provider-b.com/v1",
            "api_key": "key-b",
            "context_window": 128000
        })
        
        assert len(config.custom_models) == 3
        
        # Remove Provider A
        removed = config.remove_custom_provider("ProviderA", "https://api.provider-a.com/v1")
        assert removed == 2
        assert len(config.custom_models) == 1
        assert config.custom_models[0]["model_id"] == "b-1"
        
        # Remove Provider B
        removed = config.remove_custom_provider("ProviderB", "https://api.provider-b.com/v1")
        assert removed == 1
        assert len(config.custom_models) == 0
    finally:
        config.custom_models = original_models


def test_last_project_folder_and_sync(tmp_path):
    from fastapi.testclient import TestClient
    from utim_cli.server.router import app
    from utim_cli.server.db import User, init_db, SessionLocal
    from utim_cli.server.auth import create_user
    from utim_cli.bootstrap import _sync_global_experience
    import shutil
    
    init_db()
    db = SessionLocal()
    try:
        # Clean up existing test user
        db.query(User).filter(User.email == "test_folder@utim.dev").delete()
        db.commit()
        
        user = create_user(db, "test_folder@utim.dev", "Folder User")
        client = TestClient(app)
        headers = {"X-API-Key": user.api_key}
        
        # 1. Test GET last-folder (should be None initially)
        resp = client.get("/api/auth/last-folder", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["folder_path"] is None
        
        # 2. Test POST last-folder
        prev_folder_dir = tmp_path / "prev_project"
        prev_folder_dir.mkdir()
        
        resp = client.post(
            "/api/auth/last-folder",
            headers=headers,
            json={"folder_path": str(prev_folder_dir)}
        )
        assert resp.status_code == 200
        assert resp.json()["folder_path"] == str(prev_folder_dir)
        
        # Verify it persisted
        db.refresh(user)
        assert user.last_project_folder == str(prev_folder_dir)
        
        # 3. Setup files in prev_project
        prev_utim = prev_folder_dir / ".utim"
        prev_utim.mkdir()
        prev_exp = prev_utim / "experiences.json"
        prev_exp.write_text('["exp1"]', encoding="utf-8")
        
        prev_vector = prev_utim / "vector_db"
        prev_vector.mkdir()
        (prev_vector / "data.db").write_text("chromadb data", encoding="utf-8")
        
        prev_meta = prev_utim / "vector_meta_exp.json"
        prev_meta.write_text('{"hash": "123"}', encoding="utf-8")
        
        # Current folder setup
        curr_folder_dir = tmp_path / "curr_project"
        curr_folder_dir.mkdir()
        
        # Mock/Override SERVER_URL in bootstrap to talk to our TestClient
        import requests
        original_get = requests.get
        original_post = requests.post
        
        def mock_get(url, *args, **kwargs):
            if "/auth/last-folder" in url:
                return client.get("/api/auth/last-folder", headers=headers)
            return original_get(url, *args, **kwargs)
            
        def mock_post(url, *args, **kwargs):
            if "/auth/last-folder" in url:
                return client.post("/api/auth/last-folder", headers=headers, json=kwargs.get("json"))
            return original_post(url, *args, **kwargs)
            
        requests.get = mock_get
        requests.post = mock_post
        
        try:
            # Run sync
            _sync_global_experience(user.api_key, str(curr_folder_dir))
            
            # Verify server state is updated with the current folder
            resp = client.get("/api/auth/last-folder", headers=headers)
            assert resp.json()["folder_path"] == str(curr_folder_dir)
            
        finally:
            requests.get = original_get
            requests.post = original_post
            
    finally:
        db.query(User).filter(User.email == "test_folder@utim.dev").delete()
        db.commit()
        db.close()


def test_consecutive_rewind_reverts_to_original_state(tmp_path):
    from utim_cli.orchestrator import Orchestrator
    from rich.console import Console
    
    test_file = tmp_path / "code.py"
    # Initial state
    test_file.write_text("state0")
    
    c = Console()
    orch = Orchestrator(c)
    
    # Simulate turn history with consecutive edits to the same file
    turn1 = {
        "user_msg": "User message 1",
        "msg_start": 0,
        "msg_end": 2,
        "changes": [
            {
                "path": str(test_file),
                "action": "edit_file",
                "before": "state0",
                "after": "state1"
            }
        ]
    }
    
    turn2 = {
        "user_msg": "User message 2",
        "msg_start": 2,
        "msg_end": 4,
        "changes": [
            {
                "path": str(test_file),
                "action": "edit_file",
                "before": "state1",
                "after": "state2"
            }
        ]
    }
    
    orch.turn_history = [turn1, turn2]
    orch.messages = [
        {"role": "user", "content": "hi1"},
        {"role": "assistant", "content": "ans1"},
        {"role": "user", "content": "hi2"},
        {"role": "assistant", "content": "ans2"}
    ]
    
    # We update the file to the final state "state2"
    test_file.write_text("state2")
    
    # Rewind to turn 0 (first turn), which should revert BOTH turn1 and turn2
    res = orch.rewind_to_turn(0, revert_code=True, revert_msgs=True)
    
    # Check that it successfully reverted to "state0" (the state before the reverted turns began)
    assert test_file.read_text() == "state0"
    assert len(orch.turn_history) == 0
    assert len(orch.messages) == 0


def test_context_compression_passes_is_reflection_flag():
    from unittest.mock import patch
    from utim_cli.context_pruner import _call_compression_model_with_fallback
    
    with patch("utim_cli.client_utils.proxy_openrouter_request") as mock_proxy:
        mock_proxy.return_value.status_code = 200
        mock_proxy.return_value.json.return_value = {
            "choices": [{"message": {"content": "Summary content"}}]
        }
        
        res = _call_compression_model_with_fallback(
            messages=[{"role": "user", "content": "test content"}],
            llm_key="test-key",
            content_hint="test-hint",
            primary_model="test-model"
        )
        
        # Verify proxy_openrouter_request was called with is_reflection=True
        mock_proxy.assert_called()
        args, kwargs = mock_proxy.call_args
        assert kwargs.get("is_reflection") is True


def test_hint_command_caches_hint():
    from utim_cli.utim import _handle_command, STATE
    from utim_cli.orchestrator import Orchestrator
    from rich.console import Console
    from unittest.mock import MagicMock
    
    # Test running /hint with a message
    c = Console()
    orch = Orchestrator(c)
    mock_app = MagicMock()
    
    # Clear any existing hint
    STATE.pop("hint", None)
    
    _handle_command("/hint u are checking the wrong file", orch, mock_app)
    
    assert STATE.get("hint") == "u are checking the wrong file"


def test_skills_situational_scoring_and_deduplication():
    from unittest.mock import patch
    from pathlib import Path
    from utim_cli.orchestrator import get_system_prompt

    # Provide a controlled set of skills so the test is isolated from the
    # developer's local .utim/skills/ directory (which has underscore-named
    # variants that may partially match and are NOT marked as read by the mock).
    _fake_skills = {
        "terminal-ui-design": {
            "name": "terminal-ui-design",
            "description": "Guidelines for terminal UI design",
            "keywords": ["terminal", "ui", "design", "menu", "rich", "layout"],
            "path": Path(".agents/skills/terminal-ui-design/SKILL.md"),
        }
    }

    with patch("utim_cli.orchestrator._get_active_task", side_effect=lambda x: x), \
         patch("utim_cli.bootstrap.scan_available_skills", return_value=_fake_skills):

        # Verify that a design-related prompt recommends the TUI skill
        sys_prompt = get_system_prompt(user_prompt="I want to design a beautiful terminal menu ui")
        assert "terminal-ui-design" in sys_prompt
        assert "ACTIVE WORKSPACE SKILLS RECOMMENDED" in sys_prompt

        # Verify that if the user prompt is casual or does not match any skill, no recommendation is injected
        sys_prompt_casual = get_system_prompt(user_prompt="hello agent")
        assert "ACTIVE WORKSPACE SKILLS RECOMMENDED" not in sys_prompt_casual

        # Verify that if the skill has already been read via tool_calls, the recommendation disappears
        mock_messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "view_file",
                            "arguments": '{"AbsolutePath": "C:/path/to/.agents/skills/terminal-ui-design/SKILL.md"}'
                        }
                    }
                ]
            },
            {
                "role": "tool",
                "name": "view_file",
                "tool_call_id": "call_1",
                "content": "description: terminal ui design\n---\nTerminal UI Design Skill Content"
            }
        ]
        sys_prompt_read = get_system_prompt(
            user_prompt="terminal menu ui",
            messages=mock_messages
        )
        assert "terminal-ui-design" not in sys_prompt_read, (
            "Expected terminal-ui-design to be suppressed after it was read in tool_calls, "
            f"but found it in system prompt."
        )
        assert "ACTIVE WORKSPACE SKILLS RECOMMENDED" not in sys_prompt_read, (
            "Expected ACTIVE WORKSPACE SKILLS RECOMMENDED to be absent once all skills are read."
        )


def test_skills_compression_in_place():
    from utim_cli.orchestrator import Orchestrator
    from rich.console import Console
    from unittest.mock import patch
    
    c = Console()
    orch = Orchestrator(c)
    
    # Populate messages with a tool output representing an uncompressed skill read
    skill_content = "---\nname: test-skill\ndescription: A test skill for testing compression\n---\nRules:\n1. Rule one\n2. Rule two"
    orch.messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "design something"},
        {"role": "assistant", "content": "I will read the skill.", "tool_calls": []},
        {
            "role": "tool",
            "name": "view_file",
            "content": skill_content
        },
        {"role": "user", "content": "next task"}
    ]
    
    # Mock fallback compression request
    with patch("utim_cli.context_pruner._call_compression_model_with_fallback") as mock_compress:
        mock_compress.return_value = "Compressed skill summary content: rule one and rule two."
        
        orch._compress_intra_turn(turn_msg_start=1)
        
        # Verify call parameters
        mock_compress.assert_called()
        
        # Verify content was updated in-place
        assert "RELEVANT CORE SKILL: TEST-SKILL (COMPRESSED)" in orch.messages[3]["content"]
        assert "Compressed skill summary content" in orch.messages[3]["content"]


def test_auth_login_conditional_restart():
    from unittest.mock import patch, MagicMock
    import utim_cli.auth as auth
    import os
    
    auth._IS_TEST = True
    
    # 1. Test case: running inside test environment (pytest present in sys.argv)
    # The execv call should NOT be made.
    with patch("requests.get") as mock_get, \
         patch("requests.post") as mock_post, \
         patch("os.execv") as mock_execv, \
         patch("subprocess.call") as mock_subcall, \
         patch("sys.exit") as mock_exit, \
         patch("sys.argv", ["pytest", "tests/"]), \
         patch("sys.__stdout__") as mock_stdout:
        
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "device_code": "devcode123",
            "user_code": "usr123",
            "verify_url": "https://api.utim.dev/verify",
            "expires_in": 600
        }
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "email": "test@utim.dev",
            "user_id": "123",
            "display_name": "Test User"
        }
        
        # We simulate user pasting an API key
        with patch("builtins.input", side_effect=["sk-testapikey"]):
            auth.login()
            
        mock_execv.assert_not_called()
        mock_subcall.assert_not_called()
        
    # 2. Test case: running outside test environment (non-pytest environment)
    with patch("requests.get") as mock_get, \
         patch("requests.post") as mock_post, \
         patch("os.execv") as mock_execv, \
         patch("subprocess.Popen") as mock_popen, \
         patch("subprocess.call") as mock_subcall, \
         patch("sys.exit") as mock_exit, \
         patch("sys.argv", ["C:\\path with spaces\\utim.py", "task", "hello world"]), \
         patch.dict("os.environ", {}, clear=True), \
         patch("sys.__stdout__") as mock_stdout:
        
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "device_code": "devcode123",
            "user_code": "usr123",
            "verify_url": "https://api.utim.dev/verify",
            "expires_in": 600
        }
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "email": "test@utim.dev",
            "user_id": "123",
            "display_name": "Test User"
        }
        
        with patch("builtins.input", side_effect=["sk-testapikey"]):
            auth.login()
            
        mock_popen.assert_called_once()
        mock_exit.assert_called_once_with(0)
        
        # Verify the target command was resolved to run with python -m
        args_called = mock_popen.call_args[0][0]
        if isinstance(args_called, list):
            assert args_called[1] == "-m" or "python" in args_called[0]
        else:
            assert "-m utim_cli.utim" in args_called


def test_image_generation_quota_bypass():
    from fastapi.testclient import TestClient
    from unittest.mock import patch, MagicMock
    import pytest
    from utim_cli.server.router import app
    from utim_cli.server.db import User, QuotaUsage, Credit, init_db, SessionLocal
    from utim_cli.server.auth import create_user

    IMAGE_CREDITS_COST = 80.0   # flat rate per image generation (see endpoint)
    FREE_PLAN_IMAGE_LIMIT = 3000.0  # free plan limit for image endpoint

    init_db()
    db = SessionLocal()
    try:
        # Create fresh user for this test
        db.query(User).filter(User.email == "test_img_quota@utim.dev").delete()
        db.commit()

        user = create_user(db, "test_img_quota@utim.dev", "Img Quota User")
        headers = {"X-API-Key": user.api_key}

        # 1. Exhaust the free-plan image quota.
        #    The image endpoint enforces FREE_PLAN_IMAGE_LIMIT (3000 credits), NOT
        #    quota.credits_limit (100 credits). Set credits_used and free_monthly_used above the image gate.
        quota = db.query(QuotaUsage).filter(QuotaUsage.user_id == user.id).first()
        quota.credits_used = FREE_PLAN_IMAGE_LIMIT + 1.0   # 3001 > 3000 → quota exceeded

        # Ensure bonus_balance is 0 so the gate actually fires
        credit_row = db.query(Credit).filter(Credit.user_id == user.id).first()
        if not credit_row:
            credit_row = Credit(user_id=user.id, balance=0.0, bonus_balance=0.0, free_monthly_used=FREE_PLAN_IMAGE_LIMIT + 1.0)
            db.add(credit_row)
        else:
            credit_row.bonus_balance = 0.0
            credit_row.balance = 0.0
            credit_row.free_monthly_used = FREE_PLAN_IMAGE_LIMIT + 1.0
        db.commit()

        client = TestClient(app)

        # 2. Call /completions/images/generations → should get 429 (quota exceeded)
        resp = client.post("/completions/images/generations", json={
            "prompt": "sunset over mountains",
            "model": "black-forest-labs/flux.2-klein-4b"
        }, headers=headers)
        assert resp.status_code == 429, (
            f"Expected 429 quota exceeded but got {resp.status_code}: {resp.json()}"
        )
        assert "quota exceeded" in resp.json()["detail"]["message"].lower()

        # 3. Give user bonus balance — this should unlock image generation
        db.refresh(credit_row)
        credit_row.bonus_balance = 1000.0
        db.commit()

        # Mock requests.post to simulate a successful NVIDIA NIM API call
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"url": "https://example.com/test.png"}]}

        with patch("requests.post", return_value=mock_response), \
             patch.dict("os.environ", {
                 "NVIDIA_API_KEY": "mock_nv_key",
                 "OPENROUTER_API_KEY": "mock_or_key"
             }):
            resp = client.post("/completions/images/generations", json={
                "prompt": "sunset over mountains",
                "model": "black-forest-labs/flux.2-klein-4b"
            }, headers=headers)

            assert resp.status_code == 200, (
                f"Expected 200 with bonus balance but got {resp.status_code}: {resp.json()}"
            )
            assert resp.json()["data"][0]["url"] == "https://example.com/test.png"

            # 4. Verify credit deduction: IMAGE_CREDITS_COST should be deducted from bonus_balance
            db.refresh(credit_row)
            assert credit_row.bonus_balance == pytest.approx(1000.0 - IMAGE_CREDITS_COST, abs=1.0), (
                f"Expected bonus_balance to decrease by {IMAGE_CREDITS_COST}. "
                f"Got {credit_row.bonus_balance}"
            )
    finally:
        db.close()


def test_preferred_quota_free_plan_premium_gating():
    from fastapi.testclient import TestClient
    from unittest.mock import patch, MagicMock
    from utim_cli.server.router import app
    from utim_cli.server.db import User, Credit, init_db, SessionLocal
    from utim_cli.server.auth import create_user

    init_db()
    db = SessionLocal()
    try:
        db.query(User).filter(User.email == "test_gating_pref@utim.dev").delete()
        db.commit()

        user = create_user(db, "test_gating_pref@utim.dev", "Gating User")
        headers = {"X-API-Key": user.api_key}

        # Set user credit with bonus balance
        credit_row = db.query(Credit).filter(Credit.user_id == user.id).first()
        credit_row.bonus_balance = 500.0
        credit_row.balance = 100.0
        db.commit()

        client = TestClient(app)

        # Case 1: Premium model, preferred_quota = "regular" -> HTTP 403 Forbidden with custom error
        resp = client.post("/completions", json={
            "messages": [{"role": "user", "content": "hello"}],
            "model_id": "anthropic/claude-sonnet-4.6",  # Premium (no :free suffix)
            "preferred_quota": "regular"
        }, headers=headers)
        
        assert resp.status_code == 403
        assert "With your current plan you can't use premium models with your quota provided by the free plan" in resp.json()["detail"]

        # Case 2: Premium model, preferred_quota = "bonus" -> allowed (mock AsyncOpenAI client)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].delta = MagicMock()
        mock_response.choices[0].delta.content = "mock response content"
        mock_response.usage = None
        
        async def mock_stream(*args, **kwargs):
            class AsyncGen:
                async def __aiter__(self):
                    yield mock_response
            return AsyncGen()

        with patch("utim_cli.server.routes.completion_routes.AsyncOpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create = mock_stream
            mock_openai_cls.return_value = mock_client

            resp2 = client.post("/completions", json={
                "messages": [{"role": "user", "content": "hello"}],
                "model_id": "anthropic/claude-sonnet-4.6",
                "preferred_quota": "bonus"
            }, headers=headers)
            
            list(resp2.iter_lines())
            assert resp2.status_code == 200

    finally:
        db.query(User).filter(User.email == "test_gating_pref@utim.dev").delete()
        db.commit()
        db.close()


def test_preferred_quota_deduction_ordering():
    from fastapi.testclient import TestClient
    from unittest.mock import patch, MagicMock
    from utim_cli.server.router import app
    from utim_cli.server.db import User, Credit, UserSubscription, Plan, init_db, SessionLocal
    from utim_cli.server.auth import create_user
    from utim_cli.server.routes.quota_routes import activate_subscription

    init_db()
    db = SessionLocal()
    try:
        db.query(User).filter(User.email == "test_order_pref@utim.dev").delete()
        db.commit()

        user = create_user(db, "test_order_pref@utim.dev", "Order User")
        headers = {"X-API-Key": user.api_key}

        # Mock OpenRouter/NVIDIA responses
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].delta = MagicMock()
        mock_response.choices[0].delta.content = "mock response content"
        mock_response.usage = None
        
        async def mock_stream(*args, **kwargs):
            class AsyncGen:
                async def __aiter__(self):
                    yield mock_response
            return AsyncGen()

        client = TestClient(app)

        with patch("utim_cli.server.routes.completion_routes.AsyncOpenAI") as mock_openai_cls, \
             patch("utim_cli.server.routes.completion_routes.estimate_cost", return_value=50.0):
            mock_client = MagicMock()
            mock_client.chat.completions.create = mock_stream
            mock_openai_cls.return_value = mock_client

            # --- PART 1: Free Plan ---
            # Set balances: balance = 100.0, bonus_balance = 100.0
            credit_row = db.query(Credit).filter(Credit.user_id == user.id).first()
            credit_row.balance = 100.0
            credit_row.bonus_balance = 100.0
            credit_row.free_monthly_used = 0.0
            db.commit()

            # Case A: preferred_quota = "regular" -> deducts 50.0 from balance first
            resp = client.post("/completions", json={
                "messages": [{"role": "user", "content": "hello"}],
                "model_id": "cohere/north-mini-code:free",
                "preferred_quota": "regular"
            }, headers=headers)
            list(resp.iter_lines())
            
            db.refresh(credit_row)
            assert credit_row.balance == 50.0
            assert credit_row.bonus_balance == 100.0

            # Reset balances
            credit_row.balance = 100.0
            credit_row.bonus_balance = 100.0
            credit_row.free_monthly_used = 0.0
            db.commit()

            # Case B: preferred_quota = "bonus" -> deducts 50.0 from bonus_balance first
            resp = client.post("/completions", json={
                "messages": [{"role": "user", "content": "hello"}],
                "model_id": "cohere/north-mini-code:free",
                "preferred_quota": "bonus"
            }, headers=headers)
            list(resp.iter_lines())
            
            db.refresh(credit_row)
            assert credit_row.balance == 100.0
            assert credit_row.bonus_balance == 50.0

            # --- PART 2: Paid Plan (Hobby) ---
            activate_subscription(db, user_id=user.id, plan_id="hobby")
            
            # Reset balances to known state
            db.refresh(credit_row)
            credit_row.balance = 100.0
            credit_row.bonus_balance = 100.0
            
            # Set sub_row current_cycle_used to 0
            sub_row = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
            sub_row.current_cycle_used = 0.0
            db.commit()

            # Case C: preferred_quota = "regular" -> deducts 50.0 from cycle allowance first
            resp = client.post("/completions", json={
                "messages": [{"role": "user", "content": "hello"}],
                "model_id": "anthropic/claude-sonnet-4.6",
                "preferred_quota": "regular"
            }, headers=headers)
            list(resp.iter_lines())
            
            db.refresh(credit_row)
            db.refresh(sub_row)
            cycle_allowance = 4000 / 144.0
            assert sub_row.current_cycle_used == pytest.approx(cycle_allowance)
            assert credit_row.balance == pytest.approx(100.0 - (50.0 - cycle_allowance))
            assert credit_row.bonus_balance == 100.0

            # Reset current_cycle_used and balances
            sub_row.current_cycle_used = 0.0
            credit_row.balance = 100.0
            credit_row.bonus_balance = 100.0
            db.commit()

            # Case D: preferred_quota = "bonus" -> deducts 50.0 from bonus_balance first
            resp = client.post("/completions", json={
                "messages": [{"role": "user", "content": "hello"}],
                "model_id": "anthropic/claude-sonnet-4.6",
                "preferred_quota": "bonus"
            }, headers=headers)
            list(resp.iter_lines())
            
            db.refresh(credit_row)
            db.refresh(sub_row)
            assert sub_row.current_cycle_used == 0.0
            assert credit_row.balance == 100.0
            assert credit_row.bonus_balance == 50.0

    finally:
        # Cleanup subscription and user
        db.query(UserSubscription).filter(UserSubscription.user_id == user.id).delete()
        db.query(User).filter(User.email == "test_order_pref@utim.dev").delete()
        db.commit()
        db.close()


def test_bonus_quota_limits():
    from utim_cli.server.db import User, Credit, init_db, SessionLocal, get_max_bonus_limit
    from utim_cli.server.auth import create_user
    from utim_cli.server.routes.quota_routes import activate_subscription
    
    init_db()
    db = SessionLocal()
    try:
        # Clean up existing test user
        db.query(User).filter(User.email == "bonus_limit_test@utim.dev").delete()
        db.commit()
        
        user = create_user(db, "bonus_limit_test@utim.dev", "Limit Test User")
        credit = db.query(Credit).filter(Credit.user_id == user.id).first()
        
        # 1. Verify get_max_bonus_limit values
        assert get_max_bonus_limit("free") == 20000.0
        assert get_max_bonus_limit("hobby") == 50000.0
        assert get_max_bonus_limit("pro") == 1500000.0
        assert get_max_bonus_limit("max") == 3000000.0
        assert get_max_bonus_limit("ultimate") == 4500000.0
        
        # 2. Set high bonus values manually
        credit.bonus_balance = 2000000.0
        credit.bonus_limit = 2000000.0
        db.commit()
        
        # 3. Activate subscription to Hobby -> should cap at 50,000
        activate_subscription(db, user_id=user.id, plan_id="hobby")
        db.refresh(credit)
        assert credit.bonus_balance == 50000.0
        assert credit.bonus_limit == 50000.0
        
    finally:
        db.query(User).filter(User.email == "bonus_limit_test@utim.dev").delete()
        db.commit()
        db.close()
