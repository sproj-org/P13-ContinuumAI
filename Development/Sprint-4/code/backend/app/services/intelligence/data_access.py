"""Data access helpers shared by orchestration, prediction, and segmentation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.query import AggregateFilter, _build_where_clause, _quote_identifier
from app.core.mart_registry import get_mart
from app.services.intelligence.specs import MetricAggregation, SpecFilter, TimeGrain

OUT_DIR = Path(__file__).resolve().parents[3] / "out"
TEMPORAL_ROLES = {"datetime", "temporal"}
DIMENSION_ROLES = {"dimension", "text", "id", "boolean", *TEMPORAL_ROLES}
NUMERIC_PHYSICAL_TYPES = {"int", "float", "decimal", "numeric", "double", "real", "bigint", "smallint"}
TIME_GRAIN_TO_PERIOD = {
    "day": "D",
    "week": "W",
    "month": "M",
    "quarter": "Q",
    "year": "Y",
}


def _unique_columns(columns: list[str]) -> list[str]:
    output: list[str] = []
    for column in columns:
        if column not in output:
            output.append(column)
    return output


def load_mart_profile(dataset_id: str, table: str) -> dict[str, Any]:
    mart = get_mart(dataset_id, table)
    profile_path = OUT_DIR / str(mart["profile_file"])
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail=f"Profile file not found for table '{table}'")
    return json.loads(profile_path.read_text(encoding="utf-8"))


def column_profiles(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for item in profile.get("columns", []):
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            output[str(item["name"])] = item
    return output


def _column_role(column: dict[str, Any]) -> str:
    return str(column.get("effective_role") or column.get("base_role") or "").lower()


def _column_physical_type(column: dict[str, Any]) -> str:
    return str(column.get("physical_type") or "").lower()


def measure_columns(profile: dict[str, Any]) -> list[str]:
    return [
        name
        for name, column in column_profiles(profile).items()
        if _column_role(column) == "measure" and _column_physical_type(column) in NUMERIC_PHYSICAL_TYPES
    ]


def dimension_columns(profile: dict[str, Any]) -> list[str]:
    return [name for name, column in column_profiles(profile).items() if _column_role(column) in DIMENSION_ROLES]


def temporal_columns(profile: dict[str, Any]) -> list[str]:
    return [name for name, column in column_profiles(profile).items() if _column_role(column) in TEMPORAL_ROLES]


def _looks_temporal_name(value: str) -> bool:
    normalized = value.lower()
    return any(token in normalized for token in ("date", "day", "week", "month", "quarter", "year"))


def resolve_time_field(profile: dict[str, Any], preferred: str | None = None) -> str | None:
    columns = column_profiles(profile)
    if preferred and preferred in columns:
        preferred_column = columns[preferred]
        if _column_role(preferred_column) in TEMPORAL_ROLES or _looks_temporal_name(preferred):
            return preferred
    temporal = temporal_columns(profile)
    if preferred and preferred in temporal:
        return preferred
    if temporal:
        return temporal[0]
    for candidate in ("sales_date", "snapshot_date", "first_tx_date", "last_tx_date", "first_date", "last_date"):
        if candidate in columns:
            return candidate
    return None


def resolve_entity_field(profile: dict[str, Any], preferred: str | None = None) -> str | None:
    columns = column_profiles(profile)
    if preferred and preferred in columns:
        return preferred
    candidates = [
        "customer_id",
        "store_id",
        "sku_id",
        "product_id",
        "salesperson_id",
        "region",
        "segment",
        "city",
    ]
    for candidate in candidates:
        if candidate in columns:
            return candidate
    ids = [name for name in columns if name.endswith("_id")]
    return ids[0] if ids else None


def resolve_feature_columns(
    profile: dict[str, Any],
    *,
    preferred: list[str] | None = None,
    exclude: set[str] | None = None,
    limit: int = 6,
) -> list[str]:
    columns = measure_columns(profile)
    exclude = exclude or set()
    preferred = preferred or []
    output: list[str] = []
    for candidate in preferred:
        if candidate in columns and candidate not in exclude and candidate not in output:
            output.append(candidate)
    for candidate in columns:
        if candidate in exclude or candidate in output:
            continue
        output.append(candidate)
        if len(output) >= limit:
            break
    return output


def _to_aggregate_filters(filters: list[SpecFilter]) -> list[AggregateFilter]:
    op_map = {
        "=": "eq",
        "!=": "ne",
        ">": "gt",
        ">=": "gte",
        "<": "lt",
        "<=": "lte",
        "in": "in",
        "between": "in",
    }
    output: list[AggregateFilter] = []
    for item in filters:
        if item.op == "between" and isinstance(item.value, list) and len(item.value) == 2:
            output.append(AggregateFilter(column=item.field, op="gte", value=item.value[0]))
            output.append(AggregateFilter(column=item.field, op="lte", value=item.value[1]))
            continue
        output.append(AggregateFilter(column=item.field, op=op_map[item.op], value=item.value))
    return output


def fetch_frame(
    *,
    dataset_id: str,
    table: str,
    columns: list[str],
    filters: list[SpecFilter],
    db: Session,
    limit: int | None = None,
) -> pd.DataFrame:
    mart = get_mart(dataset_id, table)
    profile = load_mart_profile(dataset_id, table)
    valid_columns = set(column_profiles(profile).keys())
    selected_columns = _unique_columns([column for column in columns if column in valid_columns])
    if not selected_columns:
        return pd.DataFrame()

    where_clause, params = _build_where_clause(_to_aggregate_filters(filters), valid_columns)
    sql = f"""
        SELECT {", ".join(_quote_identifier(column) for column in selected_columns)}
        FROM "{mart["schema"]}"."{table}"
        {where_clause}
    """
    if limit is not None:
        sql += "\nLIMIT :limit"
        params["limit"] = max(1, min(limit, 20000))

    statement = text(sql)
    rows = db.execute(statement, params).fetchall()
    if not rows:
        return pd.DataFrame(columns=selected_columns)
    return pd.DataFrame(rows, columns=selected_columns)


def resolve_metric_series(frame: pd.DataFrame, metric: str) -> pd.Series | None:
    if frame.empty or not metric or metric not in frame.columns:
        return None

    selection = frame.loc[:, frame.columns == metric]
    if isinstance(selection, pd.Series):
        return selection
    if selection.empty:
        return None

    # Duplicate columns typically come from repeated SELECTs of the same physical field.
    # Prefer the first populated series and backfill from later duplicates if needed.
    series = selection.iloc[:, 0].copy()
    for index in range(1, selection.shape[1]):
        series = series.combine_first(selection.iloc[:, index])
    return series


def aggregate_time_series(
    frame: pd.DataFrame,
    *,
    time_field: str,
    metric: str,
    aggregation: MetricAggregation,
    grain: TimeGrain,
    group_by: list[str] | None = None,
) -> pd.DataFrame:
    if frame.empty or time_field not in frame.columns:
        return pd.DataFrame(columns=["period_start", "period_label", "value"])

    working = frame.copy()
    working[time_field] = pd.to_datetime(working[time_field], errors="coerce", utc=True)
    working = working.dropna(subset=[time_field])
    if working.empty:
        return pd.DataFrame(columns=["period_start", "period_label", "value"])
    working[time_field] = working[time_field].dt.tz_localize(None)

    metric_series = resolve_metric_series(working, metric)
    if aggregation == "count":
        if metric_series is not None:
            working["__metric_source__"] = metric_series
            working = working.dropna(subset=["__metric_source__"])
        working["__metric__"] = 1.0
    else:
        if metric_series is None:
            return pd.DataFrame(columns=["period_start", "period_label", "value"])
        working["__metric__"] = pd.to_numeric(metric_series, errors="coerce")
        working = working.dropna(subset=["__metric__"])
    if working.empty:
        return pd.DataFrame(columns=["period_start", "period_label", "value"])

    period_code = TIME_GRAIN_TO_PERIOD[grain]
    working["period_start"] = working[time_field].dt.to_period(period_code).dt.start_time
    group_columns = ["period_start", *(group_by or [])]

    if aggregation == "avg":
        grouped = working.groupby(group_columns, dropna=False)["__metric__"].mean().reset_index(name="value")
    elif aggregation == "min":
        grouped = working.groupby(group_columns, dropna=False)["__metric__"].min().reset_index(name="value")
    elif aggregation == "max":
        grouped = working.groupby(group_columns, dropna=False)["__metric__"].max().reset_index(name="value")
    else:
        grouped = working.groupby(group_columns, dropna=False)["__metric__"].sum().reset_index(name="value")

    grouped["period_label"] = grouped["period_start"].dt.strftime("%Y-%m-%d")
    if grain == "month":
        grouped["period_label"] = grouped["period_start"].dt.strftime("%Y-%m")
    elif grain == "quarter":
        grouped["period_label"] = grouped["period_start"].dt.to_period("Q").astype(str)
    elif grain == "year":
        grouped["period_label"] = grouped["period_start"].dt.strftime("%Y")
    return grouped.sort_values(group_columns).reset_index(drop=True)


def summarize_metric(series: pd.Series) -> dict[str, float]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return {"min": 0.0, "max": 0.0, "mean": 0.0}
    return {
        "min": float(numeric.min()),
        "max": float(numeric.max()),
        "mean": float(numeric.mean()),
    }
