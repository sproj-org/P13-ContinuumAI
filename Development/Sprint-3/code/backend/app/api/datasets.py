"""Dataset-scoped API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.charts import router as charts_router
from app.api.strategy import router as strategy_router
from app.api.profiling import (
    ChartDataRequest,
    get_chart_data_for_dataset,
    get_column_profile_for_dataset,
    get_table_profile_for_dataset,
    list_aggregations_for_dataset,
)
from app.api.query import router as query_router
from app.db.database import get_db
from app.schemas.chart_data import LegacyChartDataResponse

router = APIRouter(prefix="/datasets/{dataset_id}", tags=["datasets"])
router.include_router(query_router)
router.include_router(charts_router)
router.include_router(strategy_router)


@router.get("/profiling/aggregations")
def list_dataset_aggregations(dataset_id: str):
    return list_aggregations_for_dataset(dataset_id)


@router.get("/profiling/aggregations/{table_name}/profile")
def get_dataset_table_profile(dataset_id: str, table_name: str):
    return get_table_profile_for_dataset(dataset_id, table_name)


@router.get("/profiling/aggregations/{table_name}/columns/{column_name}")
def get_dataset_column_profile(dataset_id: str, table_name: str, column_name: str):
    return get_column_profile_for_dataset(dataset_id, table_name, column_name)


@router.post("/profiling/chart-data", response_model=LegacyChartDataResponse)
def get_dataset_chart_data(
    dataset_id: str,
    request: ChartDataRequest,
    db: Session = Depends(get_db),
):
    return get_chart_data_for_dataset(dataset_id, request, db)
