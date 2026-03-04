"""Debug-only API routes."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/openai")
def get_openai_debug_status():
    settings = get_settings()
    if not settings.ENABLE_DEBUG:
        raise HTTPException(status_code=404, detail="Not found")

    vizagent_model = os.getenv("VIZAGENT_MODEL") or settings.OPENAI_MODEL or None
    return {
        "openai_configured": bool((settings.OPENAI_API_KEY or "").strip()),
        "vizagent_model": vizagent_model,
    }
