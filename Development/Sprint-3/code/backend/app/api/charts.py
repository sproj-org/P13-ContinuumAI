"""Dataset-scoped chart preview API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.services.charts.models import ChartPreviewResponse, ChartSpecV1
from app.services.charts.spec_resolver import execute_chart_preview

router = APIRouter(prefix="/charts", tags=["charts"])


@router.post("/preview", response_model=ChartPreviewResponse)
def preview_chart(
    dataset_id: str,
    request: ChartSpecV1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    return execute_chart_preview(dataset_id=dataset_id, chart_spec=request, db=db)
