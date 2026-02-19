"""Dataset-scoped strategy API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.db.models import User
from app.services.strategy.kpi_registry import list_kpis

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.get("/kpis")
def get_dataset_kpis(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    return {"kpis": list_kpis(dataset_id)}
