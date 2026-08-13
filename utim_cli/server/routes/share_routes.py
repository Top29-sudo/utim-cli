import os
import uuid
import datetime
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..auth import get_current_user
from ..db import User, Plan, SharedPackage, get_db
from ..storage_nodes import StorageNodeManager, GoogleDriveStorageNode

router = APIRouter(prefix="/shares", tags=["shares"])
logger = logging.getLogger("utim.routes.shares")


def _clean_expired_db(db: Session) -> None:
    """Delete expired SharedPackage rows and their Drive files (background task)."""
    try:
        now = datetime.datetime.utcnow()
        expired = db.query(SharedPackage).filter(SharedPackage.expires_at < now).all()
        for pkg in expired:
            try:
                provider = GoogleDriveStorageNode(pkg.node_id, f"Node {pkg.node_id}")
                provider.delete(pkg.drive_file_id)
            except Exception:
                pass
            db.delete(pkg)
        if expired:
            db.commit()
            logger.info(f"Cleaned up {len(expired)} expired shared packages.")
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to clean expired shares: {e}")


@router.post("/upload")
async def upload_share(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    expires: str = Form("1h"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    True zero-RAM streaming share upload.

    Memory profile:
      - Server RAM used = one 8 MB Drive chunk at a time (constant)
      - No matter if the file is 100 MB or 5 GB, peak RAM stays ~8–16 MB
      - The client request body is read 64 KB at a time and forwarded
        immediately into the Google Drive resumable upload session

    Flow:
      1. Read Content-Length header (sent by client) to tell Drive how big
         the upload will be (required for resumable session init).
      2. Open a Drive resumable upload session → get session URI.
      3. Stream client chunks (64 KB) through a sha256 counter.
      4. When the 8 MB Drive block is full, flush it to Drive.
      5. Send the final partial block as the terminal chunk.
      6. Persist DB record with final size + sha256.
    """
    # Run expiry cleanup in background so it doesn't slow the upload
    background_tasks.add_task(_clean_expired_db, db)

    # Determine user's plan and share limit
    sub = user.subscription
    plan = sub.plan if sub else None
    if not plan:
        plan_id_for_query = sub.plan_id if sub else "free"
        plan = db.query(Plan).filter(Plan.id == plan_id_for_query).first()

    plan_key = (plan.id or "free").lower() if plan else "free"

    limit_map = {
        "free":         1024 * 1024 * 1024,                    # 1 GB
        "hobby":        2 * 1024 * 1024 * 1024,                # 2 GB
        "pro":          3 * 1024 * 1024 * 1024,                # 3 GB
        "starter":      3 * 1024 * 1024 * 1024,                # 3 GB
        "max":          int(4.5 * 1024 * 1024 * 1024),         # 4.5 GB
        "professional": int(4.5 * 1024 * 1024 * 1024),         # 4.5 GB
        "ultimate":     5 * 1024 * 1024 * 1024,                # 5 GB
    }
    limit_bytes = limit_map.get(plan_key, 1024 * 1024 * 1024)

    # Content-Length declared by the client (requests_toolbelt sends this).
    # Drive's resumable API needs it upfront.  If absent (chunked TE) we use
    # limit_bytes as the upper bound — Drive accepts * in that case too.
    declared_size: int = 0
    try:
        cl = file.headers.get("content-length") or file.size
        if cl:
            declared_size = int(cl)
    except Exception:
        declared_size = 0

    if declared_size and declared_size > limit_bytes:
        limit_gb = limit_bytes / (1024 ** 3)
        raise HTTPException(
            status_code=413,
            detail=(
                f"Shared package size exceeds the limit for your plan "
                f"({limit_gb:.1f} GB). Please upgrade your plan."
            ),
        )

    share_id = f"share_{uuid.uuid4().hex[:12]}"
    now = datetime.datetime.utcnow()
    expiry_deltas = {
        "15m": datetime.timedelta(minutes=15),
        "1h":  datetime.timedelta(hours=1),
        "4h":  datetime.timedelta(hours=4),
        "1d":  datetime.timedelta(days=1),
        "3d":  datetime.timedelta(days=3),
        "7d":  datetime.timedelta(days=7),
    }
    delta      = expiry_deltas.get(expires, datetime.timedelta(hours=1))
    expires_at = now + delta

    # ── True streaming pipeline ────────────────────────────────────────────
    # Build an async generator that reads the UploadFile 64 KB at a time,
    # enforces the plan size cap on the fly, and tracks bytes + sha256.
    import hashlib as _hashlib

    READ_CHUNK  = 64 * 1024   # 64 KB reads from the client socket
    sha256_h    = _hashlib.sha256()
    file_size   = 0
    first_bytes = bytearray()
    MAGIC_CHECK = 4  # bytes needed to verify ZIP magic

    async def _async_chunk_iter():
        """Async generator: yields bytes read from the UploadFile."""
        nonlocal file_size
        while True:
            chunk = await file.read(READ_CHUNK)
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > limit_bytes:
                limit_gb = limit_bytes / (1024 ** 3)
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"Shared package size exceeds the limit for your plan "
                        f"({limit_gb:.1f} GB). Please upgrade your plan."
                    ),
                )
            sha256_h.update(chunk)
            if len(first_bytes) < MAGIC_CHECK:
                first_bytes.extend(chunk[:MAGIC_CHECK - len(first_bytes)])
            yield chunk

    # upload_stream() is synchronous (runs requests.put internally) so we
    # must convert our async generator to a sync iterator that runs the
    # async reads on the current event loop via run_until_complete.
    import asyncio

    loop = asyncio.get_event_loop()

    def _sync_chunk_iter():
        """Convert the async generator to a synchronous iterator."""
        gen = _async_chunk_iter()
        while True:
            try:
                # Drive runs in a background thread — use run_coroutine_threadsafe
                # if we're off the main thread, else use loop.run_until_complete.
                try:
                    fut = asyncio.ensure_future(gen.__anext__(), loop=loop)
                    chunk = loop.run_until_complete(asyncio.wait_for(fut, timeout=120))
                    yield chunk
                except asyncio.TimeoutError:
                    raise RuntimeError("Client stalled: no data received for 120 seconds during upload.")
            except StopAsyncIteration:
                break

    # Select storage node before starting the stream (needs file_size estimate)
    try:
        node_record = StorageNodeManager.select_best_node(db, declared_size or limit_bytes)
        provider    = GoogleDriveStorageNode(node_record.id, node_record.account_label)
    except Exception as e:
        logger.error(f"No storage node available: {e}")
        raise HTTPException(status_code=503, detail=f"No storage node available: {e}")

    # Stream directly to Drive — zero full-file buffering
    try:
        upload_meta  = provider.upload_stream(
            package_id = share_id,
            filename   = file.filename or f"{share_id}.zip",
            size_bytes = declared_size or 0,
            chunk_iter = _sync_chunk_iter(),
            sha256_hex = "",   # computed inside the generator
        )
        drive_file_id = upload_meta["drive_file_id"]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Streaming upload to storage node failed: {e}")
        raise HTTPException(status_code=500, detail=f"Storage node upload failed: {e}")

    # Validate: empty body or non-ZIP
    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail="Received an empty file. The upload connection may have dropped. Please try again.",
        )
    if bytes(first_bytes[:4]) != b"PK\x03\x04":
        # Cleanup orphaned Drive file
        try:
            provider.delete(drive_file_id)
        except Exception:
            pass
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is not a valid ZIP archive. Re-package and try again.",
        )

    sha256_hex = sha256_h.hexdigest()

    # Persist metadata to PostgreSQL
    try:
        pkg = SharedPackage(
            id           = share_id,
            user_id      = user.id,
            filename     = file.filename or f"{share_id}.zip",
            node_id      = node_record.id,
            drive_file_id= drive_file_id,
            size_bytes   = file_size,
            sha256       = sha256_hex or upload_meta.get("sha256"),
            created_at   = now,
            expires_at   = expires_at,
        )
        db.add(pkg)
        db.commit()
    except Exception as e:
        db.rollback()
        try:
            provider.delete(drive_file_id)
        except Exception:
            pass
        logger.error(f"Failed to persist share record to DB: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save share metadata: {e}")

    server_url = os.environ.get("SERVER_URL", "https://api.utim.dev").rstrip("/")
    link = f"{server_url}/shares/download/{share_id}"

    return {
        "success":    True,
        "link":       link,
        "expires_at": expires_at.isoformat() + "Z",
    }




@router.get("/download/{share_id}")
async def download_share(
    share_id: str,
    db: Session = Depends(get_db),
):
    # Look up in DB — this survives redeploys unlike meta.json
    pkg = db.query(SharedPackage).filter(SharedPackage.id == share_id).first()

    if not pkg:
        raise HTTPException(
            status_code=404,
            detail="Shared package does not exist or has expired.",
        )

    if pkg.is_expired:
        # Async cleanup in DB + Drive
        try:
            provider = GoogleDriveStorageNode(pkg.node_id, f"Node {pkg.node_id}")
            provider.delete(pkg.drive_file_id)
        except Exception:
            pass
        try:
            db.delete(pkg)
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(status_code=410, detail="This shared package has expired.")

    try:
        provider = GoogleDriveStorageNode(pkg.node_id, f"Node {pkg.node_id}")
        stream = provider.stream_download(pkg.drive_file_id)

        safe_filename = (pkg.filename or f"{share_id}.zip").replace('"', "").replace("\\", "").replace("/", "")
        if not safe_filename:
            safe_filename = f"{share_id}.zip"

        headers = {
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "X-Package-Checksum": pkg.sha256 or "",
            "Content-Type": "application/octet-stream",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
        if pkg.size_bytes:
            headers["Content-Length"] = str(pkg.size_bytes)

        return StreamingResponse(stream, media_type="application/octet-stream", headers=headers)

    except FileNotFoundError:
        logger.error(f"Drive file not found for share {share_id}: drive_file_id={pkg.drive_file_id}")
        raise HTTPException(
            status_code=404,
            detail="Shared package file not found on storage node. It may have been deleted from Drive.",
        )
    except Exception as e:
        logger.error(f"Error streaming shared package {share_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Storage streaming error: {e}")


@router.delete("/delete/{share_id}")
async def delete_share(
    share_id: str,
    db: Session = Depends(get_db),
):
    pkg = db.query(SharedPackage).filter(SharedPackage.id == share_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Shared package not found.")

    try:
        provider = GoogleDriveStorageNode(pkg.node_id, f"Node {pkg.node_id}")
        provider.delete(pkg.drive_file_id)
    except Exception as e:
        logger.warning(f"Failed to delete shared file from Google Drive node: {e}")

    db.delete(pkg)
    db.commit()
    return {"success": True, "detail": "Shared package deleted successfully."}


@router.get("/list")
async def list_shares(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all non-expired shares for the authenticated user."""
    now = datetime.datetime.utcnow()
    packages = (
        db.query(SharedPackage)
        .filter(SharedPackage.user_id == user.id, SharedPackage.expires_at > now)
        .order_by(SharedPackage.created_at.desc())
        .all()
    )
    return [
        {
            "id": p.id,
            "filename": p.filename,
            "size_bytes": p.size_bytes,
            "created_at": p.created_at.isoformat() + "Z",
            "expires_at": p.expires_at.isoformat() + "Z",
            "link": f"{os.environ.get('SERVER_URL', 'https://api.utim.dev').rstrip('/')}/shares/download/{p.id}",
        }
        for p in packages
    ]
