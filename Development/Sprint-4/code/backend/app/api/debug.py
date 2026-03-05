"""Debug-only API routes."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/openai")
def get_openai_debug_status():
    settings = get_settings()
    if not settings.ENABLE_DEBUG:
        raise HTTPException(status_code=404, detail="Not found")

    key = (settings.OPENAI_API_KEY or "").strip()
    fingerprint = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8] if key else "none"
    model = settings.OPENAI_MODEL or None
    return {
        "openai_configured": bool(key),
        "openai_model": model,
        "key_fingerprint": fingerprint,
        "vizagent_model": model,
    }
