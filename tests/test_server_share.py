import io
import os
import shutil
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient

from utim_cli.server.router import app
from utim_cli.server.routes.share_routes import STORAGE_DIR, META_FILE

def test_server_sharing_endpoints():
    # Make sure storage dir is clean
    if STORAGE_DIR.exists():
        shutil.rmtree(STORAGE_DIR)
    STORAGE_DIR.mkdir(exist_ok=True)

    from utim_cli.server.auth import get_current_user
    from utim_cli.server.db import User

    def mock_get_current_user():
        return User(id="test_user_id", email="test@example.com", api_key="test_key", is_active=True)

    app.dependency_overrides[get_current_user] = mock_get_current_user
    client = TestClient(app)

    # 1. Create a dummy zip in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zipf:
        zipf.writestr("test.txt", "hello server share")
    zip_bytes = zip_buffer.getvalue()

    # 2. Test POST /shares/upload
    response = client.post(
        "/shares/upload",
        files={"file": ("test_share.zip", zip_bytes, "application/zip")},
        data={"expires": "15m"}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert "link" in res_data
    assert "expires_at" in res_data

    # Extract share_id from link
    link = res_data["link"]
    share_id = link.split("/")[-1]

    # 3. Test GET /shares/download/{share_id}
    download_resp = client.get(f"/shares/download/{share_id}")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/zip"
    
    # Read downloaded zip
    downloaded_buffer = io.BytesIO(download_resp.content)
    with zipfile.ZipFile(downloaded_buffer, "r") as zipf:
        assert "test.txt" in zipf.namelist()
        assert zipf.read("test.txt").decode('utf-8') == "hello server share"

    # 4. Test nonexistent share download
    bad_resp = client.get("/shares/download/share_nonexistent")
    assert bad_resp.status_code == 404

    # Cleanup
    app.dependency_overrides.clear()
    if STORAGE_DIR.exists():
        shutil.rmtree(STORAGE_DIR)
