import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from utim_cli.server.router import app
from utim_cli.server.db import get_db, User, Credit, QuotaUsage, SessionLocal
from utim_cli.server.routes.completion_routes import ACTIVE_COMPLETION_TASKS

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_cancel_completion_endpoint(db_session: Session):
    # Setup mock user and check database
    user = db_session.query(User).filter(User.email == "test@utim.dev").first()
    if not user:
        user = User(
            id="test-cancel-user-id",
            email="test@utim.dev",
            api_key="test-cancel-api-key",
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    client = TestClient(app)
    headers = {"X-API-Key": user.api_key}

    # Verify no active task exists initially
    response = client.post(
        "/completions/cancel",
        json={"session_id": "test-session-123"},
        headers=headers
    )
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert "No active request found" in response.json()["message"]

    # Mock registering a dummy task
    class DummyTask:
        def __init__(self):
            self.is_cancelled = False
        def cancel(self):
            self.is_cancelled = True

    dummy = DummyTask()
    key = (user.id, "test-session-123")
    ACTIVE_COMPLETION_TASKS[key] = (dummy, db_session)

    try:
        # Cancel the task using the cancel endpoint
        response = client.post(
            "/completions/cancel",
            json={"session_id": "test-session-123"},
            headers=headers
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "cancelled successfully" in response.json()["message"]
        assert dummy.is_cancelled is True
    finally:
        ACTIVE_COMPLETION_TASKS.pop(key, None)
