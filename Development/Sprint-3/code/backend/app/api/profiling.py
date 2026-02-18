"""
Profiling API endpoints.
Serves pre-generated profile JSON files from backend/out and chart data from DB.
Legacy /api/profiling routes are kept as aliases for dataset_id='silkroute'.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.mart_registry import (
    DEFAULT_DATASET_ID,
    get_mart,
    is_supported_dataset,
    list_marts,
)
from app.db.database import get_db
from app.schemas.chart_data import LegacyChartDataResponse
from app.services.charts.models import ChartSpecV1
from app.services.charts.spec_resolver import execute_chart_preview
from services.profiling.json_sanitize import sanitize_for_json

router = APIRouter(prefix="/profiling", tags=["profiling"])

OUT_DIR = Path(__file__).resolve().parents[2] / "out"


def _validate_dataset_id(dataset_id: str) -> None:
    if not is_supported_dataset(dataset_id):
        raise HTTPException(status_code=404, detail=f"Unknown dataset_id '{dataset_id}'")


def _get_profile_path(dataset_id: str, table_name: str) -> Path:
    try:
        mart = get_mart(dataset_id, table_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found") from exc

    profile_file = str(mart["profile_file"])
    return OUT_DIR / profile_file


class ChartDataRequest(BaseModel):
    """Request body for chart data query."""

    table_name: str
    x_axis: str
    y_axis: str
    aggregation_fn: Literal["sum", "avg", "count", "min", "max"] = "sum"
    limit: int = 20

    @field_validator("table_name", "x_axis", "y_axis")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", value):
            raise ValueError(f"Invalid identifier: {value}")
        return value

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("limit must be >= 1")
        if value > 5000:
            raise ValueError("limit must be <= 5000")
        return value


def load_profile(dataset_id: str, table_name: str) -> dict:
    """Load a profile JSON file for the given table."""
    _validate_dataset_id(dataset_id)

    file_path = _get_profile_path(dataset_id, table_name)
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Profile file for '{table_name}' not found",
        )

    try:
        with file_path.open("r", encoding="utf-8") as handle:
            profile = json.load(handle)
            return sanitize_for_json(profile)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing profile for '{table_name}': {exc}",
        ) from exc


def list_aggregations_for_dataset(dataset_id: str) -> dict:
    """List all available aggregation tables with summary info."""
    _validate_dataset_id(dataset_id)
    aggregations = []

    for mart in list_marts(dataset_id):
        table_name = str(mart["id"])
        try:
            profile = load_profile(dataset_id, table_name)
        except HTTPException:
            continue

        item = {
            "table_name": profile.get("table_name") or profile.get("dataset_name") or table_name,
            "schema_name": profile.get("schema_name", mart.get("schema", "aggregations")),
            "row_count": profile.get("row_count", 0),
            "column_count": profile.get("column_count", 0),
            "profiled_at": profile.get("profiled_at", ""),
            "label": mart.get("label"),
            "description": mart.get("description"),
        }
        aggregations.append(item)

    return sanitize_for_json({"aggregations": aggregations})


def get_table_profile_for_dataset(dataset_id: str, table_name: str) -> dict:
    profile = load_profile(dataset_id, table_name)
    return sanitize_for_json(profile)


def get_column_profile_for_dataset(dataset_id: str, table_name: str, column_name: str) -> dict:
    profile = load_profile(dataset_id, table_name)

    columns = profile.get("columns", [])
    for col in columns:
        if col.get("name") == column_name:
            return sanitize_for_json(col)

    raise HTTPException(
        status_code=404,
        detail=f"Column '{column_name}' not found in table '{table_name}'",
    )


def _legacy_request_to_chart_spec(dataset_id: str, request: ChartDataRequest) -> ChartSpecV1:
    return ChartSpecV1(
        version="v1",
        dataset_id=dataset_id,
        table=request.table_name,
        chart={"type": "bar"},
        encoding={
            "x": {"field": request.x_axis},
            "y": [
                {
                    "field": request.y_axis,
                    "aggregation": request.aggregation_fn,
                }
            ],
        },
        filters=[],
        sort=[{"field": "agg_value", "direction": "desc"}],
        limit=request.limit,
    )


def get_chart_data_for_dataset(
    dataset_id: str,
    request: ChartDataRequest,
    db: Session,
) -> LegacyChartDataResponse:
    """
    Query aggregated data from mart tables for chart visualization.
    """
    _validate_dataset_id(dataset_id)

    chart_spec = _legacy_request_to_chart_spec(dataset_id=dataset_id, request=request)
    preview_payload = execute_chart_preview(dataset_id=dataset_id, chart_spec=chart_spec, db=db)
    rows = preview_payload.get("rows", [])

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No data found for the specified query",
        )

    metric_column = chart_spec.encoding.y[0].alias or "agg_value"
    raw_x_values = [row.get(request.x_axis) for row in rows]
    raw_y_values = [row.get(metric_column) for row in rows]
    agg_fn = request.aggregation_fn.upper()
    title = f"{agg_fn}({request.y_axis}) by {request.x_axis}"

    payload = {
        "x": raw_x_values,
        "y": raw_y_values,
        "title": title,
        "x_axis_label": request.x_axis,
        "y_axis_label": f"{agg_fn}({request.y_axis})",
    }
    payload = sanitize_for_json(payload)

    # Keep response_model contract stable.
    x_values = [str(value) if value is not None else "NULL" for value in payload.get("x", [])]
    y_values = [float(value) if value is not None else 0.0 for value in payload.get("y", [])]

    response_payload = {
        "x": x_values,
        "y": y_values,
        "title": str(payload["title"]),
        "x_axis_label": str(payload["x_axis_label"]),
        "y_axis_label": str(payload["y_axis_label"]),
    }
    response_payload = sanitize_for_json(response_payload)
    return LegacyChartDataResponse.model_validate(response_payload)


@router.get("/aggregations")
def list_aggregations():
    return list_aggregations_for_dataset(DEFAULT_DATASET_ID)


@router.get("/aggregations/{table_name}/profile")
def get_table_profile(table_name: str):
    return get_table_profile_for_dataset(DEFAULT_DATASET_ID, table_name)


@router.get("/aggregations/{table_name}/columns/{column_name}")
def get_column_profile(table_name: str, column_name: str):
    return get_column_profile_for_dataset(DEFAULT_DATASET_ID, table_name, column_name)


@router.post("/chart-data", response_model=LegacyChartDataResponse)
def get_chart_data(request: ChartDataRequest, db: Session = Depends(get_db)):
    return get_chart_data_for_dataset(DEFAULT_DATASET_ID, request, db)
