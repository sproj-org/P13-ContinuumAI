"""Dataset-scoped API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.charts import router as charts_router
from app.api.chat import router as chat_router
from app.api.analysis import router as analysis_router
from app.api.strategy import router as strategy_router
from app.api.profiling import (
    ChartDataRequest,
    get_chart_data_for_dataset,
    get_column_profile_for_dataset,
    get_table_profile_for_dataset,
    list_aggregations_for_dataset,
)
from app.api.query import router as query_router
from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import OrganizationDataset, User
from app.schemas.chart_data import LegacyChartDataResponse
from app.services.agents.mart_context import build_chat_hints

router = APIRouter(prefix="/datasets", tags=["datasets"])
dataset_router = APIRouter(prefix="/{dataset_id}", tags=["datasets"])
dataset_router.include_router(query_router)
dataset_router.include_router(charts_router)
dataset_router.include_router(strategy_router)
dataset_router.include_router(chat_router)
dataset_router.include_router(analysis_router)


@router.get("/available")
def get_available_datasets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return active datasets that the current user's organization can access."""
    if current_user.organization_id is None:
        return {"datasets": ["silkroute"]}

    rows = (
        db.query(OrganizationDataset.dataset_id)
        .filter(
            OrganizationDataset.organization_id == current_user.organization_id,
            OrganizationDataset.is_active.is_(True),
        )
        .all()
    )

    dataset_ids = sorted({row[0] for row in rows if row and row[0]})
    if not dataset_ids:
        dataset_ids = ["silkroute"]

    return {"datasets": dataset_ids}


@dataset_router.get("/profiling/aggregations")
def list_dataset_aggregations(dataset_id: str):
    return list_aggregations_for_dataset(dataset_id)


@dataset_router.get("/profiling/aggregations/{table_name}/profile")
def get_dataset_table_profile(dataset_id: str, table_name: str):
    return get_table_profile_for_dataset(dataset_id, table_name)


@dataset_router.get("/profiling/aggregations/{table_name}/columns/{column_name}")
def get_dataset_column_profile(dataset_id: str, table_name: str, column_name: str):
    return get_column_profile_for_dataset(dataset_id, table_name, column_name)


@dataset_router.post("/profiling/chart-data", response_model=LegacyChartDataResponse)
def get_dataset_chart_data(
    dataset_id: str,
    request: ChartDataRequest,
    db: Session = Depends(get_db),
):
    return get_chart_data_for_dataset(dataset_id, request, db)


@dataset_router.get("/marts/{table}/chat-hints")
def get_dataset_chat_hints(
    dataset_id: str,
    table: str,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    return build_chat_hints(dataset_id=dataset_id, table=table)


router.include_router(dataset_router)
