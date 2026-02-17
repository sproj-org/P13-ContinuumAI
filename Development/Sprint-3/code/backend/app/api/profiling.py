"""
Profiling API endpoints.
Serves pre-generated profile JSON files from the out/ directory.
Also provides chart data querying from the database.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.mart_registry import get_mart_by_id, is_valid_mart_id, list_marts
from app.db.database import get_db
from services.profiling.json_sanitize import sanitize_for_json

router = APIRouter(prefix="/profiling", tags=["profiling"])

OUT_DIR = Path(__file__).parent.parent.parent / "out"
MARTS_SCHEMA = "marts"  # Fallback only if registry lookup fails.
ALLOWED_AGGREGATIONS = {"sum", "avg", "count", "min", "max"}
INVENTORY_NON_FINITE_COLUMNS = {"days_of_inventory", "adj_days_of_inventory"}


def get_profile_path(table_name: str) -> Path:
    mart = get_mart_by_id(table_name)
    if not mart:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    profile_file = str(mart["profile_file"])
    return OUT_DIR / profile_file


# ============================================
# Chart Data Models
# ============================================


class ChartDataRequest(BaseModel):
    """Request body for chart data query."""

    table_name: str
    x_axis: str
    y_axis: str
    aggregation_fn: Literal["sum", "avg", "count", "min", "max"] = "sum"
    limit: int = 20

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, v: str) -> str:
        if not is_valid_mart_id(v):
            raise ValueError(f"Invalid table name: {v}")
        return v

    @field_validator("x_axis", "y_axis")
    @classmethod
    def validate_column_name(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError(f"Invalid column name: {v}")
        return v


class ChartDataPoint(BaseModel):
    """Single data point for chart."""

    x: str
    y: float


class ChartDataResponse(BaseModel):
    """Response for chart data query."""

    x: list[str]
    y: list[float]
    title: str
    x_axis_label: str
    y_axis_label: str


def load_profile(table_name: str) -> dict:
    """Load a profile JSON file for the given table."""
    file_path = get_profile_path(table_name)
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Profile file for '{table_name}' not found",
        )

    try:
        with file_path.open("r", encoding="utf-8") as f:
            profile = json.load(f)
            return sanitize_for_json(profile)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing profile for '{table_name}': {exc}",
        ) from exc


@router.get("/aggregations")
def list_aggregations():
    """List all available aggregation tables with summary info."""
    aggregations = []

    for mart in list_marts():
        table_name = str(mart["id"])
        try:
            profile = load_profile(table_name)
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

    return {"aggregations": aggregations}


@router.get("/aggregations/{table_name}/profile")
def get_table_profile(table_name: str):
    """Get the full profile for a specific table."""
    profile = load_profile(table_name)
    profile = sanitize_for_json(profile)
    return profile


@router.get("/aggregations/{table_name}/columns/{column_name}")
def get_column_profile(table_name: str, column_name: str):
    """Get the profile for a specific column in a table."""
    profile = load_profile(table_name)

    columns = profile.get("columns", [])
    for col in columns:
        if col.get("name") == column_name:
            return sanitize_for_json(col)

    raise HTTPException(
        status_code=404,
        detail=f"Column '{column_name}' not found in table '{table_name}'",
    )


# ============================================
# Chart Data Endpoints
# ============================================


def validate_column_exists(table_name: str, column_name: str) -> bool:
    """Validate that a column exists in the table profile."""
    try:
        profile = load_profile(table_name)
    except HTTPException:
        return False

    columns = profile.get("columns", [])
    return any(col.get("name") == column_name for col in columns)


def get_column_profile_info(table_name: str, column_name: str) -> Optional[dict]:
    """Get column profile information including role and type."""
    try:
        profile = load_profile(table_name)
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
    role = column_profile.get("effective_role", column_profile.get("base_role", "dimension"))
    physical_type = column_profile.get("physical_type", "string")
    column_name = column_profile.get("name", "unknown")

    if aggregation_fn == "count":
        return True, ""

    if aggregation_fn in ["sum", "avg"]:
        if role != "measure":
            return (
                False,
                (
                    f"Cannot apply {aggregation_fn.upper()} to '{column_name}' - "
                    f"it's a {role}, not a measure. Try using COUNT instead, "
                    "or select a numeric column like revenue, quantity, or amount."
                ),
            )

        numeric_types = ["int", "float", "decimal", "numeric", "double", "real", "bigint", "smallint"]
        if not any(nt in physical_type.lower() for nt in numeric_types):
            return (
                False,
                (
                    f"Cannot apply {aggregation_fn.upper()} to '{column_name}' - "
                    f"column type '{physical_type}' is not numeric."
                ),
            )

        return True, ""

    if aggregation_fn in ["min", "max"]:
        if role in ["measure", "datetime"]:
            return True, ""
        if role in ["dimension", "id", "text", "boolean"]:
            return True, ""
        return True, ""

    return True, ""


def serialize_value(val):
    """Convert database values to JSON-serializable types."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val) if val.is_finite() else None
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    return val


@router.post("/chart-data", response_model=ChartDataResponse)
def get_chart_data(request: ChartDataRequest, db: Session = Depends(get_db)):
    """
    Query aggregated data from mart tables for chart visualization.

    This endpoint executes a GROUP BY query on the specified table,
    grouping by x_axis column and aggregating y_axis column.
    """
    x_column_profile = get_column_profile_info(request.table_name, request.x_axis)
    if not x_column_profile:
        raise HTTPException(
            status_code=400,
            detail=f"Column '{request.x_axis}' not found in table '{request.table_name}'",
        )

    y_column_profile = get_column_profile_info(request.table_name, request.y_axis)
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

    agg_fn = request.aggregation_fn.upper()
    mart = get_mart_by_id(request.table_name)
    schema_name = str(mart["schema"]) if mart else MARTS_SCHEMA

    y_column_ref = f'"{request.y_axis}"'
    y_sql_expr = y_column_ref
    if (
        request.table_name == "gold_inventory_health_daily"
        and request.y_axis in INVENTORY_NON_FINITE_COLUMNS
    ):
        y_sql_expr = (
            f"CASE WHEN {y_column_ref} IS NULL THEN NULL "
            f"WHEN lower(({y_column_ref})::text) IN ('infinity', '-infinity', 'nan', 'inf', '-inf') "
            f"THEN NULL ELSE {y_column_ref} END"
        )

    query = text(
        f"""
        SELECT
            CAST("{request.x_axis}" AS TEXT) as x_value,
            {agg_fn}({y_sql_expr}) as y_value
        FROM {schema_name}."{request.table_name}"
        WHERE "{request.x_axis}" IS NOT NULL
        GROUP BY "{request.x_axis}"
        ORDER BY y_value DESC
        LIMIT :limit
    """
    )

    try:
        result = db.execute(query, {"limit": request.limit})
        rows = result.fetchall()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {exc}",
        ) from exc

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No data found for the specified query",
        )

    raw_x_values = [serialize_value(row[0]) for row in rows]
    raw_y_values = [serialize_value(row[1]) for row in rows]
    title = f"{agg_fn}({request.y_axis}) by {request.x_axis}"

    payload = {
        "x": raw_x_values,
        "y": raw_y_values,
        "title": title,
        "x_axis_label": request.x_axis,
        "y_axis_label": f"{agg_fn}({request.y_axis})",
    }
    payload = sanitize_for_json(payload)

    # Keep response_model contract stable (x: list[str], y: list[float]).
    payload["x"] = [str(v) if v is not None else "NULL" for v in payload.get("x", [])]
    payload["y"] = [float(v) if v is not None else 0.0 for v in payload.get("y", [])]

    return ChartDataResponse(
        x=payload["x"],
        y=payload["y"],
        title=payload["title"],
        x_axis_label=payload["x_axis_label"],
        y_axis_label=payload["y_axis_label"],
    )
