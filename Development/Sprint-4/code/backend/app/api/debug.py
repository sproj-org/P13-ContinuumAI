"""Debug-only API routes."""

from __future__ import annotations

<<<<<<< HEAD
=======
import os

>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
from fastapi import APIRouter, HTTPException

from app.core.config import get_settings

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/openai")
def get_openai_debug_status():
    settings = get_settings()
    if not settings.ENABLE_DEBUG:
        raise HTTPException(status_code=404, detail="Not found")

<<<<<<< HEAD
    return {
        "openai_configured": bool((settings.OPENAI_API_KEY or "").strip()),
        "vizagent_model": settings.OPENAI_MODEL or None,
=======
    vizagent_model = os.getenv("VIZAGENT_MODEL") or settings.OPENAI_MODEL or None
    return {
        "openai_configured": bool((settings.OPENAI_API_KEY or "").strip()),
        "vizagent_model": vizagent_model,
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
    }
