"""Quick smoke tests for the read_file path-embedded range parser, orchestrator aliases, run_command panel rendering, and 5-hour quota checks."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rich.console import Console
from utim_cli.orchestrator import Orchestrator

console = Console(color_system="truecolor", width=100)
orch = Orchestrator(console)

# ── Test run_command rendering with ANSI escape codes and carriage returns ───
raw_result = (
    "[exit_code: 0]\n"
    "[stdout]\n"
    "vite v6.4.3 building for production...\r\n"
    "transforming... \r"
    "transforming... \r\n"
    "\x1b[32m✓\x1b[39m 2084 modules transformed.\r\n"
    "[stderr]\n"
    "  } \x1b[31mUnexpected token\x1b[39m\n"
)

try:
    print("Testing _render_result with run_command style output:")
    orch._render_result("run_command", {"command": "npm run build"}, raw_result, "yellow")
    print("✓  run_command rendering completed without errors")
except Exception as e:
    import traceback
    print(f"✗  run_command rendering failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# ── Test edit_file rendering works when user_confirmed is True ───
try:
    print("\nTesting _render_result for edit_file with user_confirmed=True:")
    orch._render_result("edit_file", {"filepath": "src/components/Navigation.tsx", "old_str": "old content\nline 2", "new_str": "new content\nline 2"}, "dummy", "green", user_confirmed=True)
    print("✓  edit_file rendering completed without errors")
except Exception as e:
    import traceback
    print(f"✗  edit_file rendering failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# ── Test get_system_prompt experience retrieval and query logic ───
try:
    print("\nTesting get_system_prompt experience retrieval:")
    from utim_cli.orchestrator import get_system_prompt
    prompt = get_system_prompt("list files in directory")
    assert isinstance(prompt, str)
    print("✓  get_system_prompt completed successfully")
except Exception as e:
    import traceback
    print(f"✗  get_system_prompt failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# ── Test 5-hour quota exhaustion error via FastAPI TestClient ───
try:
    print("\nTesting 5-hour quota check via FastAPI TestClient:")
    from fastapi.testclient import TestClient
    from utim_cli.server.router import app
    from utim_cli.server.db import User, UserSubscription, Credit, Plan, init_db, SessionLocal
    from utim_cli.server.auth import create_user
    
    init_db()
    db = SessionLocal()
    
    # 1. Clean up existing test user
    db.query(User).filter(User.email == "test_5h_exhausted@utim.dev").delete()
    db.commit()
    
    # 2. Create user
    user = create_user(db, "test_5h_exhausted@utim.dev", "Test 5H User")
    
    # 3. Upgrade to paid Plan (e.g. hobby)
    sub = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
    sub.plan_id = "hobby"
    sub.status = "active"
    
    # 4. Exhaust 5-hour cycle quota
    plan = db.query(Plan).filter(Plan.id == "hobby").first()
    cycle_allowance = plan.credits_per_month / 144.0
    sub.current_cycle_used = cycle_allowance
    
    # 5. Empty quota bank (Credit balance)
    credit_row = db.query(Credit).filter(Credit.user_id == user.id).first()
    if credit_row:
        credit_row.balance = 0.0
        credit_row.bonus_balance = 0.0
        
    db.commit()
    
    client = TestClient(app)
    headers = {"X-API-Key": user.api_key}
    
    # Verify /quota returns five_hour_quota_exhausted: True
    resp = client.get("/quota", headers=headers)
    assert resp.status_code == 200
    quota_info = resp.json()
    assert quota_info["five_hour_quota_exhausted"] is True, f"Expected five_hour_quota_exhausted=True, got {quota_info}"
    print("✓  /quota correctly reports five_hour_quota_exhausted=True")
    
    # Verify /completions raises 429 with '5-hour credit quota exhausted.'
    resp = client.post("/completions", json={
        "messages": [{"role": "user", "content": "hello"}]
    }, headers=headers)
    assert resp.status_code == 429, f"Expected 429, got {resp.status_code}"
    err_detail = resp.json()["detail"]
    assert "5-hour credit quota exhausted." in err_detail["message"], f"Expected '5-hour credit quota exhausted.', got {err_detail}"
    print("✓  /completions correctly raises HTTP 429 with '5-hour credit quota exhausted.' message")
    
finally:
    db.query(User).filter(User.email == "test_5h_exhausted@utim.dev").delete()
    db.commit()
    db.close()

print("\n✅ All rendering, system prompt, and quota check tests passed successfully!")
