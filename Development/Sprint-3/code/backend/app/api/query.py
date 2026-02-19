"""Dataset-scoped aggregate query endpoint and execution helpers."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.mart_registry import get_mart, is_supported_dataset
from app.db.database import get_db
from services.profiling.json_sanitize import sanitize_for_json

router = APIRouter(prefix="/query", tags=["query"])

OUT_DIR = Path(__file__).resolve().parents[2] / "out"
ALLOWED_AGGREGATIONS = {"sum", "avg", "count", "min", "max"}
ALLOWED_FILTER_OPS = {
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "not_in",
    "like",
    "ilike",
    "contains",
    "is_null",
    "is_not_null",
}
IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
NUMERIC_PHYSICAL_TYPES = {"int", "float", "decimal", "numeric", "double", "real", "bigint", "smallint"}
GROUPABLE_BASE_ROLES = {"dimension", "datetime", "temporal", "boolean", "id", "text"}
FLAG_LIKE_RE = re.compile(r"(_flag|^is_|^has_|indicator)", re.IGNORECASE)
INVENTORY_NON_FINITE_COLUMNS = {"days_of_inventory", "adj_days_of_inventory"}


def _quote_identifier(name: str) -> str:
    if not IDENTIFIER_RE.match(name):
        raise HTTPException(status_code=400, detail=f"Invalid identifier: {name}")
    return f'"{name}"'


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value) if value.is_finite() else None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _load_table_profile(dataset_id: str, table_name: str) -> dict[str, Any]:
    try:
        mart = get_mart(dataset_id, table_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    profile_path = OUT_DIR / str(mart["profile_file"])
    if not profile_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Profile file not found for table '{table_name}'",
        )

    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed parsing profile JSON for '{table_name}': {exc}",
        ) from exc

    return sanitize_for_json(data)


def _get_column_map(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    columns = profile.get("columns", [])
    if not isinstance(columns, list):
        return {}

    mapping: dict[str, dict[str, Any]] = {}
    for item in columns:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str):
            mapping[name] = item
    return mapping


def _resolve_effective_role(column_profile: dict[str, Any]) -> str:
    role = column_profile.get("effective_role") or column_profile.get("base_role") or ""
    return str(role).lower()


def _resolve_physical_type(column_profile: dict[str, Any]) -> str:
    return str(column_profile.get("physical_type", "")).lower()


def _is_flag_like(column_name: str) -> bool:
    return bool(FLAG_LIKE_RE.search(column_name))


def _is_groupable_column(column_name: str, column_profile: dict[str, Any]) -> bool:
    role = _resolve_effective_role(column_profile)
    if role in GROUPABLE_BASE_ROLES:
        return True

    physical_type = _resolve_physical_type(column_profile)
    if _is_flag_like(column_name) and physical_type in (NUMERIC_PHYSICAL_TYPES | {"boolean"}):
        return True

    return False


def _safe_measure_expression(table_name: str, column_name: str) -> str:
    column_ref = _quote_identifier(column_name)
    if table_name == "gold_inventory_health_daily" and column_name in INVENTORY_NON_FINITE_COLUMNS:
        return (
            f"CASE WHEN {column_ref} IS NULL THEN NULL "
            f"WHEN NOT isfinite({column_ref}::double precision) THEN NULL "
            f"ELSE {column_ref} END"
        )
    return column_ref


def _build_where_clause(
    filters: list["AggregateFilter"],
    valid_columns: set[str],
) -> tuple[str, dict[str, Any]]:
    if not filters:
        return "", {}

    params: dict[str, Any] = {}
    clauses: list[str] = []

    for idx, item in enumerate(filters):
        if item.column not in valid_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Filter column '{item.column}' is not present in the table profile",
            )

        col = _quote_identifier(item.column)
        op = item.op
        param_key = f"p_{idx}"

        if op == "eq":
            clauses.append(f"{col} = :{param_key}")
            params[param_key] = item.value
        elif op == "ne":
            clauses.append(f"{col} <> :{param_key}")
            params[param_key] = item.value
        elif op == "gt":
            clauses.append(f"{col} > :{param_key}")
            params[param_key] = item.value
        elif op == "gte":
            clauses.append(f"{col} >= :{param_key}")
            params[param_key] = item.value
        elif op == "lt":
            clauses.append(f"{col} < :{param_key}")
            params[param_key] = item.value
        elif op == "lte":
            clauses.append(f"{col} <= :{param_key}")
            params[param_key] = item.value
        elif op in {"like", "ilike", "contains"}:
            if item.value is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Filter op '{op}' requires a value for column '{item.column}'",
                )
            cast_col = f"CAST({col} AS TEXT)"
            if op == "like":
                clauses.append(f"{cast_col} LIKE :{param_key}")
                params[param_key] = str(item.value)
            elif op == "ilike":
                clauses.append(f"{cast_col} ILIKE :{param_key}")
                params[param_key] = str(item.value)
            else:
                clauses.append(f"{cast_col} ILIKE :{param_key}")
                params[param_key] = f"%{item.value}%"
        elif op in {"in", "not_in"}:
            values = item.value if isinstance(item.value, list) else None
            if not values:
                raise HTTPException(
                    status_code=400,
                    detail=f"Filter op '{op}' requires a non-empty list value",
                )
            placeholders: list[str] = []
            for value_idx, value in enumerate(values):
                value_key = f"{param_key}_{value_idx}"
                placeholders.append(f":{value_key}")
                params[value_key] = value
            in_clause = ", ".join(placeholders)
            if op == "in":
                clauses.append(f"{col} IN ({in_clause})")
            else:
                clauses.append(f"{col} NOT IN ({in_clause})")
        elif op == "is_null":
            clauses.append(f"{col} IS NULL")
        elif op == "is_not_null":
            clauses.append(f"{col} IS NOT NULL")
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported filter operator: {op}")

    return "WHERE " + " AND ".join(clauses), params


class AggregateFilter(BaseModel):
    column: str
    op: str = "eq"
    value: Any = None

    @field_validator("column")
    @classmethod
    def validate_column(cls, value: str) -> str:
        if not IDENTIFIER_RE.match(value):
            raise ValueError(f"Invalid filter column name: {value}")
        return value

    @field_validator("op")
    @classmethod
    def validate_op(cls, value: str) -> str:
        normalized = value.lower().strip()
        if normalized not in ALLOWED_FILTER_OPS:
            raise ValueError(f"Invalid filter operator '{value}'. Allowed: {sorted(ALLOWED_FILTER_OPS)}")
        return normalized


class AggregateSpec(BaseModel):
    column: str | None = None
    fn: Literal["sum", "avg", "min", "max", "count"] = "count"

    @field_validator("column")
    @classmethod
    def validate_column(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value == "*":
            return value
        if not IDENTIFIER_RE.match(value):
            raise ValueError(f"Invalid aggregate column name: {value}")
        return value


class AggregateRequest(BaseModel):
    table_name: str
    x: str | None = None
    y: str | None = None
    group_by: list[str] = Field(default_factory=list)
    filters: list[AggregateFilter] = Field(default_factory=list)
    agg: AggregateSpec
    limit: int = 5000

    @field_validator("table_name", "x", "y")
    @classmethod
    def validate_identifiers(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not IDENTIFIER_RE.match(value):
            raise ValueError(f"Invalid identifier: {value}")
        return value

    @field_validator("group_by")
    @classmethod
    def validate_group_by(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not IDENTIFIER_RE.match(value):
                raise ValueError(f"Invalid group_by column: {value}")
            if value not in seen:
                cleaned.append(value)
                seen.add(value)
        return cleaned

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("limit must be >= 1")
        if value > 5000:
            raise ValueError("limit must be <= 5000")
        return value

    @model_validator(mode="after")
    def validate_agg_spec(self) -> "AggregateRequest":
        if self.agg.fn in {"sum", "avg", "min", "max"} and not self.agg.column:
            raise ValueError(f"agg.column is required when agg.fn is '{self.agg.fn}'")
        return self


def execute_aggregate_request(
    dataset_id: str,
    request: AggregateRequest,
    db: Session,
    debug: bool = False,
) -> dict[str, Any]:
    if not is_supported_dataset(dataset_id):
        raise HTTPException(status_code=404, detail=f"Unknown dataset_id '{dataset_id}'")

    try:
        mart = get_mart(dataset_id, request.table_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    profile = _load_table_profile(dataset_id, request.table_name)
    column_map = _get_column_map(profile)
    valid_columns = set(column_map.keys())

    if not valid_columns:
        raise HTTPException(
            status_code=500,
            detail=f"Table profile for '{request.table_name}' has no columns metadata",
        )

    grouping_columns: list[str] = []
    if request.x:
        grouping_columns.append(request.x)
    for column in request.group_by:
        if column not in grouping_columns:
            grouping_columns.append(column)

    for group_col in grouping_columns:
        if group_col not in valid_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Grouping column '{group_col}' not found in table profile",
            )
        column_profile = column_map[group_col]
        role = _resolve_effective_role(column_profile)
        if not _is_groupable_column(group_col, column_profile):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Grouping column '{group_col}' has role '{role}' and is not allowed "
                    "for x/group_by (expected dimension/datetime/boolean or flag-like column)"
                ),
            )

    agg_fn = request.agg.fn.lower()
    if agg_fn not in ALLOWED_AGGREGATIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported aggregation function: {agg_fn}")

    agg_column = request.agg.column
    if agg_column == "*":
        agg_column = None
    if agg_column is None and request.y and agg_fn != "count":
        agg_column = request.y

    if agg_fn != "count" and not agg_column:
        raise HTTPException(
            status_code=400,
            detail=f"Aggregation '{agg_fn}' requires an aggregate column",
        )

    agg_expr: str
    if agg_fn == "count" and not agg_column:
        agg_expr = "COUNT(*)"
    else:
        if agg_column is None:
            raise HTTPException(
                status_code=400,
                detail="Aggregate column is required for non-count aggregations",
            )

        if agg_column not in valid_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Aggregate column '{agg_column}' not found in table profile",
            )

        agg_col_profile = column_map[agg_column]
        role = _resolve_effective_role(agg_col_profile)
        physical_type = _resolve_physical_type(agg_col_profile)

        if agg_fn != "count" and role != "measure":
            raise HTTPException(
                status_code=400,
                detail=f"Column '{agg_column}' has role '{role}' and cannot be aggregated with {agg_fn}",
            )
        if agg_fn in {"sum", "avg"} and physical_type not in NUMERIC_PHYSICAL_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Column '{agg_column}' has physical_type '{physical_type}', expected numeric",
            )

        agg_expr = f"{agg_fn.upper()}({_safe_measure_expression(request.table_name, agg_column)})"

    select_parts = [f'CAST({_quote_identifier(col)} AS TEXT) AS {_quote_identifier(col)}' for col in grouping_columns]
    select_parts.append(f"{agg_expr} AS agg_value")

    where_clause, params = _build_where_clause(request.filters, valid_columns)

    group_by_clause = ""
    order_by_clause = "ORDER BY agg_value DESC"
    if grouping_columns:
        grouping_sql = ", ".join(_quote_identifier(col) for col in grouping_columns)
        group_by_clause = f"GROUP BY {grouping_sql}"
    else:
        order_by_clause = ""

    schema_name = str(mart["schema"])
    sql = f"""
        SELECT {", ".join(select_parts)}
        FROM "{schema_name}"."{request.table_name}"
        {where_clause}
        {group_by_clause}
        {order_by_clause}
        LIMIT :limit
    """
    params["limit"] = request.limit

    statement = text(sql)
    sql_debug: str | None = None
    params_debug: dict[str, Any] | None = None
    if debug:
        try:
            compiled = statement.compile(bind=db.get_bind(), compile_kwargs={"literal_binds": False})
            sql_debug = str(compiled)
        except Exception:
            sql_debug = sql
        params_debug = {key: _serialize_value(value) for key, value in params.items()}

    try:
        result = db.execute(statement, params)
        rows = result.fetchall()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Aggregate query failed: {exc}") from exc

    output_rows: list[dict[str, Any]] = []
    output_columns = grouping_columns + ["agg_value"]
    for row in rows:
        values = [_serialize_value(value) for value in row]
        output_rows.append({column: values[idx] for idx, column in enumerate(output_columns)})

    payload = {
        "columns": output_columns,
        "rows": output_rows,
        "meta": {
            "dataset_id": dataset_id,
            "schema_name": schema_name,
            "table_name": request.table_name,
            "aggregation": {
                "fn": agg_fn,
                "column": agg_column or "*",
            },
            "row_count": len(output_rows),
            "group_by": grouping_columns,
        },
    }
    if debug:
        payload["meta"]["debug"] = {
            "sql": sql_debug,
            "params": params_debug or {},
        }
    return sanitize_for_json(payload)


@router.post("/aggregate")
def aggregate_query(
    dataset_id: str,
    request: AggregateRequest,
    db: Session = Depends(get_db),
):
    return sanitize_for_json(execute_aggregate_request(dataset_id=dataset_id, request=request, db=db))
