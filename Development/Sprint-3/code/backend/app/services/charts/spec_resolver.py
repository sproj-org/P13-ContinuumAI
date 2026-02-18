"""Resolve and execute ChartSpec v1 through the aggregate engine."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.query import AggregateFilter, AggregateRequest, AggregateSpec, execute_aggregate_request
from app.core.mart_registry import get_mart, is_supported_dataset
from app.services.charts.models import ChartSpecV1, FilterSpec, SortSpec, YMetricSpec
from services.profiling.json_sanitize import sanitize_for_json

OUT_DIR = Path(__file__).resolve().parents[3] / "out"
NUMERIC_PHYSICAL_TYPES = {"int", "float", "decimal", "numeric", "double", "real", "bigint", "smallint"}
X_ALLOWED_ROLES = {"dimension", "datetime", "temporal", "id", "text", "boolean"}


@dataclass(frozen=True)
class ResolvedChartSpec:
    normalized_spec: ChartSpecV1
    aggregate_request: AggregateRequest
    x_field: str
    y_metric: YMetricSpec
    sort: list[SortSpec]


def _load_profile(dataset_id: str, table_name: str) -> dict[str, Any]:
    try:
        mart = get_mart(dataset_id, table_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    profile_path = OUT_DIR / str(mart["profile_file"])
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail=f"Profile file not found for table '{table_name}'")

    try:
        return json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed parsing profile JSON for '{table_name}': {exc}",
        ) from exc


def _column_map(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    raw_columns = profile.get("columns", [])
    if not isinstance(raw_columns, list):
        return mapping

    for raw_column in raw_columns:
        if not isinstance(raw_column, dict):
            continue
        name = raw_column.get("name")
        if isinstance(name, str):
            mapping[name] = raw_column
    return mapping


def _resolve_role(column_profile: dict[str, Any]) -> str:
    role = column_profile.get("effective_role") or column_profile.get("base_role") or ""
    return str(role).lower()


def _resolve_physical_type(column_profile: dict[str, Any]) -> str:
    return str(column_profile.get("physical_type", "")).lower()


def _to_aggregate_filters(filters: list[FilterSpec]) -> list[AggregateFilter]:
    agg_filters: list[AggregateFilter] = []
    for item in filters:
        if item.op == "=":
            agg_filters.append(AggregateFilter(column=item.field, op="eq", value=item.value))
        elif item.op == "!=":
            agg_filters.append(AggregateFilter(column=item.field, op="ne", value=item.value))
        elif item.op == ">":
            agg_filters.append(AggregateFilter(column=item.field, op="gt", value=item.value))
        elif item.op == ">=":
            agg_filters.append(AggregateFilter(column=item.field, op="gte", value=item.value))
        elif item.op == "<":
            agg_filters.append(AggregateFilter(column=item.field, op="lt", value=item.value))
        elif item.op == "<=":
            agg_filters.append(AggregateFilter(column=item.field, op="lte", value=item.value))
        elif item.op == "in":
            agg_filters.append(AggregateFilter(column=item.field, op="in", value=item.value))
        elif item.op == "between":
            values = list(item.value)
            agg_filters.append(AggregateFilter(column=item.field, op="gte", value=values[0]))
            agg_filters.append(AggregateFilter(column=item.field, op="lte", value=values[1]))
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported filter operator '{item.op}'")
    return agg_filters


def _resolve_sort_field(sort_field: str, x_field: str, y_metric: YMetricSpec) -> str:
    if sort_field == x_field:
        return x_field

    metric_field_aliases = {"agg_value", y_metric.field}
    if y_metric.alias:
        metric_field_aliases.add(y_metric.alias)
    if sort_field in metric_field_aliases:
        return "agg_value"

    raise HTTPException(
        status_code=400,
        detail=(
            f"Invalid sort field '{sort_field}'. "
            f"Allowed fields are '{x_field}', '{y_metric.field}', and 'agg_value'."
        ),
    )


def _sort_value(value: Any) -> Any:
    if value is None:
        return (1, "")
    if isinstance(value, (int, float)):
        return (0, value)
    try:
        parsed = float(value)
        return (0, parsed)
    except (TypeError, ValueError):
        return (0, str(value).lower())


def _apply_sorting(
    rows: list[dict[str, Any]],
    sort_specs: list[SortSpec],
    x_field: str,
    y_metric: YMetricSpec,
) -> list[dict[str, Any]]:
    if not sort_specs:
        return rows

    sorted_rows = list(rows)
    for spec in reversed(sort_specs):
        key_field = _resolve_sort_field(spec.field, x_field, y_metric)
        reverse = spec.direction == "desc"
        sorted_rows.sort(key=lambda row: _sort_value(row.get(key_field)), reverse=reverse)
    return sorted_rows


def resolve_chart_spec(dataset_id: str, chart_spec: ChartSpecV1) -> ResolvedChartSpec:
    if not is_supported_dataset(dataset_id):
        raise HTTPException(status_code=404, detail=f"Unknown dataset_id '{dataset_id}'")

    if chart_spec.dataset_id and chart_spec.dataset_id != dataset_id:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Chart spec dataset_id '{chart_spec.dataset_id}' does not match route "
                f"dataset_id '{dataset_id}'"
            ),
        )

    profile = _load_profile(dataset_id, chart_spec.table)
    columns = _column_map(profile)
    if not columns:
        raise HTTPException(
            status_code=500,
            detail=f"Table profile for '{chart_spec.table}' does not contain columns metadata",
        )

    x_field = chart_spec.encoding.x.field
    x_column = columns.get(x_field)
    if x_column is None:
        raise HTTPException(
            status_code=400,
            detail=f"X-axis field '{x_field}' does not exist in table '{chart_spec.table}'",
        )

    x_role = _resolve_role(x_column)
    if x_role not in X_ALLOWED_ROLES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"X-axis field '{x_field}' has role '{x_role}'. "
                "X-axis must be dimension/temporal."
            ),
        )

    y_metric = chart_spec.encoding.y[0]
    y_column = columns.get(y_metric.field)
    if y_column is None:
        raise HTTPException(
            status_code=400,
            detail=f"Y metric field '{y_metric.field}' does not exist in table '{chart_spec.table}'",
        )

    y_role = _resolve_role(y_column)
    if y_role != "measure":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Y metric field '{y_metric.field}' has role '{y_role}'. "
                "Y-axis metrics must be measure columns."
            ),
        )

    y_physical_type = _resolve_physical_type(y_column)
    if y_metric.aggregation in {"sum", "avg", "min", "max"} and y_physical_type not in NUMERIC_PHYSICAL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Aggregation '{y_metric.aggregation}' requires numeric metric column. "
                f"'{y_metric.field}' has physical_type '{y_physical_type}'."
            ),
        )

    aggregate_filters = _to_aggregate_filters(chart_spec.filters)
    agg_column = "*" if y_metric.aggregation == "count" else y_metric.field
    aggregate_request = AggregateRequest(
        table_name=chart_spec.table,
        x=x_field,
        y=y_metric.field,
        group_by=[x_field],
        filters=aggregate_filters,
        agg=AggregateSpec(column=agg_column, fn=y_metric.aggregation),
        limit=chart_spec.limit,
    )

    normalized_spec = chart_spec.model_copy(update={"dataset_id": dataset_id})
    return ResolvedChartSpec(
        normalized_spec=normalized_spec,
        aggregate_request=aggregate_request,
        x_field=x_field,
        y_metric=y_metric,
        sort=chart_spec.sort,
    )


def execute_chart_preview(dataset_id: str, chart_spec: ChartSpecV1, db: Session) -> dict[str, Any]:
    started_at = time.perf_counter()

    resolved = resolve_chart_spec(dataset_id=dataset_id, chart_spec=chart_spec)
    aggregate_payload = execute_aggregate_request(
        dataset_id=dataset_id,
        request=resolved.aggregate_request,
        db=db,
    )

    columns = list(aggregate_payload.get("columns", []))
    rows = list(aggregate_payload.get("rows", []))

    sorted_rows = _apply_sorting(rows=rows, sort_specs=resolved.sort, x_field=resolved.x_field, y_metric=resolved.y_metric)
    final_rows = sorted_rows[: resolved.normalized_spec.limit]

    metric_column_name = resolved.y_metric.alias or "agg_value"
    if columns and columns[-1] == "agg_value" and metric_column_name != "agg_value":
        remapped_rows: list[dict[str, Any]] = []
        for row in final_rows:
            new_row = {key: value for key, value in row.items() if key != "agg_value"}
            new_row[metric_column_name] = row.get("agg_value")
            remapped_rows.append(new_row)
        final_rows = remapped_rows
        columns = [*columns[:-1], metric_column_name]

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    aggregate_meta = aggregate_payload.get("meta", {})
    response = {
        "chart_spec": resolved.normalized_spec.model_dump(mode="json"),
        "columns": columns,
        "rows": final_rows,
        "meta": {
            **aggregate_meta,
            "resolver": "chartspec_v1",
            "execution_ms": elapsed_ms,
            "sort": [item.model_dump(mode="json") for item in resolved.sort],
            "metric": {
                "field": resolved.y_metric.field,
                "aggregation": resolved.y_metric.aggregation,
                "output_column": metric_column_name,
            },
        },
    }
    return sanitize_for_json(response)
