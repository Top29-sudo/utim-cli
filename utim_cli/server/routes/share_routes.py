import os
import json
import uuid
import datetime
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from ..auth import get_current_user
from ..db import User, Plan, get_db
from ..storage_nodes import StorageNodeManager, GoogleDriveStorageNode

router = APIRouter(prefix="/shares", tags=["shares"])
logger = logging.getLogger("utim.routes.shares")

STORAGE_DIR = Path("server_shares")
STORAGE_DIR.mkdir(exist_ok=True)
META_FILE = STORAGE_DIR / "meta.json"

def load_meta() -> dict:
    if META_FILE.exists():
        try:
            with open(META_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_meta(meta: dict):
    try:
        with open(META_FILE, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def clean_expired():
    """Scan and remove expired shared zips from Google Drive nodes."""
    meta = load_meta()
    now = datetime.datetime.now(datetime.timezone.utc)
    updated_meta = {}
    changed = False

    for share_id, info in meta.items():
        try:
            expires_at = datetime.datetime.fromisoformat(info["expires_at"])
            if now > expires_at:
                # Expired - delete from Google Drive node
                node_id = info.get("node_id", "node-1")
                drive_file_id = info.get("drive_file_id")
                if drive_file_id:
                    try:
                        provider = GoogleDriveStorageNode(node_id, f"Node {node_id}")
                        provider.delete(drive_file_id)
                    except Exception:
                        pass
                changed = True
            else:
                updated_meta[share_id] = info
        except Exception:
            changed = True

    if changed:
        save_meta(updated_meta)

@router.post("/upload")
async def upload_share(
    file: UploadFile = File(...),
    expires: str = Form("1h"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    clean_expired()

    # Determine user's plan and share limit
    sub = user.subscription
    plan = sub.plan if sub else None
    if not plan:
        plan_id_for_query = sub.plan_id if sub else "free"
        plan = db.query(Plan).filter(Plan.id == plan_id_for_query).first()

    plan_key = (plan.id or "free").lower() if plan else "free"
    
    limit_map = {
        "free": 75 * 1024 * 1024,
        "hobby": 150 * 1024 * 1024,
        "pro": 300 * 1024 * 1024,
        "starter": 300 * 1024 * 1024,
        "max": 500 * 1024 * 1024,
        "professional": 500 * 1024 * 1024,
        "ultimate": 1024 * 1024 * 1024,
    }
    
    limit_bytes = limit_map.get(plan_key, 75 * 1024 * 1024)
    
    # Read file bytes
    try:
        zip_bytes = await file.read()
        file_size = len(zip_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file payload: {e}")

    if file_size > limit_bytes:
        limit_mb = int(limit_bytes / (1024 * 1024))
        raise HTTPException(
            status_code=413,
            detail=f"Shared package size ({file_size / (1024 * 1024):.2f} MB) exceeds the limit for your plan ({limit_mb} MB). Please upgrade your plan."
        )

    share_id = f"share_{uuid.uuid4().hex[:12]}"
    
    now = datetime.datetime.now(datetime.timezone.utc)
    if expires == "15m":
        delta = datetime.timedelta(minutes=15)
    elif expires == "1h":
        delta = datetime.timedelta(hours=1)
    elif expires == "4h":
        delta = datetime.timedelta(hours=4)
    elif expires == "1d":
        delta = datetime.timedelta(days=1)
    elif expires == "3d":
        delta = datetime.timedelta(days=3)
    elif expires == "7d":
        delta = datetime.timedelta(days=7)
    else:
        delta = datetime.timedelta(hours=1)

    expires_at = now + delta

    # Select best healthy Google Drive node with highest available storage
    try:
        node_record = StorageNodeManager.select_best_node(db, file_size)
        provider = GoogleDriveStorageNode(node_record.id, node_record.account_label)
        upload_meta = provider.upload(share_id, zip_bytes, f"{share_id}.zip")
        drive_file_id = upload_meta["drive_file_id"]
    except Exception as e:
        logger.error(f"Failed to upload shared package to storage node: {e}")
        raise HTTPException(status_code=500, detail=f"Storage node upload failed: {e}")

    # Save metadata
    meta = load_meta()
    meta[share_id] = {
        "id": share_id,
        "filename": file.filename,
        "node_id": node_record.id,
        "drive_file_id": drive_file_id,
        "size_bytes": file_size,
        "sha256": upload_meta.get("sha256"),
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "user_id": user.id,
    }
    save_meta(meta)

    server_url = os.environ.get("SERVER_URL", "https://api.utim.dev").rstrip("/")
    link = f"{server_url}/shares/download/{share_id}"

    return {"success": True, "link": link, "expires_at": expires_at.isoformat()}

@router.get("/download/{share_id}")
async def download_share(share_id: str):
    clean_expired()

    meta = load_meta()
    if share_id not in meta:
        raise HTTPException(status_code=404, detail="Shared package does not exist or has expired.")

    info = meta[share_id]
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        expires_at = datetime.datetime.fromisoformat(info["expires_at"])
        if now > expires_at:
            clean_expired()
            raise HTTPException(status_code=410, detail="This shared package has expired.")
    except Exception:
        raise HTTPException(status_code=404, detail="Error validating share expiration.")

    node_id = info.get("node_id", "node-1")
    drive_file_id = info.get("drive_file_id")

    if not drive_file_id:
        raise HTTPException(status_code=404, detail="Shared package file ID missing.")

    try:
        provider = GoogleDriveStorageNode(node_id, f"Node {node_id}")
        stream = provider.stream_download(drive_file_id)
        filename = info.get("filename", f"{share_id}.zip")
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Package-Checksum": info.get("sha256", ""),
        }
        return StreamingResponse(stream, media_type="application/zip", headers=headers)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shared package file not found on storage node.")
    except Exception as e:
        logger.error(f"Error streaming shared package {share_id}: {e}")
        raise HTTPException(status_code=500, detail="Storage streaming error.")

@router.delete("/delete/{share_id}")
async def delete_share(share_id: str):
    meta = load_meta()
    if share_id in meta:
        info = meta[share_id]
        node_id = info.get("node_id", "node-1")
        drive_file_id = info.get("drive_file_id")
        if drive_file_id:
            try:
                provider = GoogleDriveStorageNode(node_id, f"Node {node_id}")
                provider.delete(drive_file_id)
            except Exception as e:
                logger.warning(f"Failed to delete shared file from Google Drive node: {e}")
        del meta[share_id]
        save_meta(meta)
        return {"success": True, "detail": "Shared package deleted successfully from storage node."}
    raise HTTPException(status_code=404, detail="Shared package not found.")
