"""
Profiling API endpoints.
Serves pre-generated profile JSON files from backend/out and chart data from DB.
Legacy /api/profiling routes are kept as aliases for dataset_id='silkroute'.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.api.query import AggregateRequest, AggregateSpec, execute_aggregate_request
from app.core.mart_registry import (
    DEFAULT_DATASET_ID,
    get_mart,
    is_supported_dataset,
    list_marts,
)
from app.db.database import get_db
from app.schemas.chart_data import LegacyChartDataResponse
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


def get_column_profile_info(
    dataset_id: str,
    table_name: str,
    column_name: str,
) -> Optional[dict]:
    try:
        profile = load_profile(dataset_id, table_name)
    except HTTPException:
        return None

    columns = profile.get("columns", [])
    for col in columns:
        if col.get("name") == column_name:
            return col
    return None


def validate_aggregation_compatibility(column_profile: dict, aggregation_fn: str) -> tuple[bool, str]:
    """
    Validate that the aggregation function is compatible with the column type.
    Returns (is_valid, error_message)
    """
    role = str(column_profile.get("effective_role", column_profile.get("base_role", "dimension"))).lower()
    physical_type = str(column_profile.get("physical_type", "string")).lower()
    column_name = str(column_profile.get("name", "unknown"))

    if aggregation_fn == "count":
        return True, ""

    if aggregation_fn in ["sum", "avg"]:
        if role != "measure":
            return (
                False,
                (
                    f"Cannot apply {aggregation_fn.upper()} to '{column_name}' - "
                    f"it's a {role}, not a measure. Try COUNT or choose a numeric measure."
                ),
            )

        numeric_types = ["int", "float", "decimal", "numeric", "double", "real", "bigint", "smallint"]
        if not any(nt in physical_type for nt in numeric_types):
            return (
                False,
                (
                    f"Cannot apply {aggregation_fn.upper()} to '{column_name}' - "
                    f"column type '{physical_type}' is not numeric."
                ),
            )

    return True, ""


def _chart_to_aggregate_request(request: ChartDataRequest) -> AggregateRequest:
    agg_column = "*" if request.aggregation_fn == "count" else request.y_axis
    return AggregateRequest(
        table_name=request.table_name,
        x=request.x_axis,
        y=request.y_axis,
        group_by=[request.x_axis],
        filters=[],
        agg=AggregateSpec(column=agg_column, fn=request.aggregation_fn),
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

    try:
        get_mart(dataset_id, request.table_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    x_column_profile = get_column_profile_info(dataset_id, request.table_name, request.x_axis)
    if not x_column_profile:
        raise HTTPException(
            status_code=400,
            detail=f"Column '{request.x_axis}' not found in table '{request.table_name}'",
        )

    y_column_profile = get_column_profile_info(dataset_id, request.table_name, request.y_axis)
    if not y_column_profile:
        raise HTTPException(
            status_code=400,
            detail=f"Column '{request.y_axis}' not found in table '{request.table_name}'",
        )

    is_valid, error_msg = validate_aggregation_compatibility(
        y_column_profile,
        request.aggregation_fn,
    )
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    agg_request = _chart_to_aggregate_request(request)
    aggregate_payload = execute_aggregate_request(dataset_id=dataset_id, request=agg_request, db=db)
    rows = aggregate_payload.get("rows", [])

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No data found for the specified query",
        )

    raw_x_values = [row.get(request.x_axis) for row in rows]
    raw_y_values = [row.get("agg_value") for row in rows]
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
