"""Pull a newly published edition into an ephemeral web service."""
from __future__ import annotations

import logging
import os
import secrets
import threading
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, status

from ...core.object_storage import configured, pull


router = APIRouter()
logger = logging.getLogger(__name__)
_sync_lock = threading.Lock()


def _authorized(authorization: str | None) -> bool:
    token = os.getenv("STORAGE_SYNC_TOKEN", "").strip()
    return bool(
        len(token) >= 32
        and authorization
        and secrets.compare_digest(authorization, f"Bearer {token}")
    )


@router.post("/sync")
def sync_storage(authorization: str | None = Header(default=None)):
    """Refresh local news after the cloud updater publishes a signed manifest."""
    if not _authorized(authorization):
        raise HTTPException(status_code=404, detail="Not found")
    if not configured():
        raise HTTPException(status_code=503, detail="Object storage is not configured")
    if not _sync_lock.acquire(blocking=False):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A storage refresh is already running")
    try:
        restored = pull(Path("static"))
        return {"status": "synchronized", "files_changed": restored}
    except Exception:
        logger.exception("Could not synchronize published news from object storage")
        raise HTTPException(status_code=503, detail="Storage synchronization failed")
    finally:
        _sync_lock.release()
