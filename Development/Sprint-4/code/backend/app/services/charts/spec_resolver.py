"""Resolve and execute ChartSpec v1 through the aggregate engine."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.query import (
    AggregateFilter,
    AggregateRequest,
    AggregateSpec,
    _build_where_clause,
    _quote_identifier,
    execute_aggregate_request,
)
from app.core.config import get_settings
from app.core.mart_registry import get_mart, is_supported_dataset
from app.services.cache.factory import get_cache
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
    if y_metric.aggregation != "count" and y_role != "measure":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Y metric field '{y_metric.field}' has role '{y_role}'. "
                "Y-axis metrics must be measure columns unless aggregation is count."
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


def _validate_histogram_spec(dataset_id: str, chart_spec: ChartSpecV1) -> tuple[ChartSpecV1, YMetricSpec, dict[str, Any], dict[str, dict[str, Any]]]:
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
    if x_field not in columns:
        raise HTTPException(
            status_code=400,
            detail=f"X-axis field '{x_field}' does not exist in table '{chart_spec.table}'",
        )

    y_metric = chart_spec.encoding.y[0]
    y_column = columns.get(y_metric.field)
    if y_column is None:
        raise HTTPException(
            status_code=400,
            detail=f"Y metric field '{y_metric.field}' does not exist in table '{chart_spec.table}'",
        )

    y_role = _resolve_role(y_column)
    y_physical_type = _resolve_physical_type(y_column)
    if y_role != "measure":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Histogram metric field '{y_metric.field}' has role '{y_role}'. "
                "Histogram requires a numeric measure field."
            ),
        )
    if y_physical_type not in NUMERIC_PHYSICAL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Histogram metric field '{y_metric.field}' has physical_type '{y_physical_type}'. "
                "Histogram requires a numeric measure field."
            ),
        )

    normalized_spec = chart_spec.model_copy(update={"dataset_id": dataset_id})
    return normalized_spec, y_metric, profile, columns


def _execute_histogram_preview(dataset_id: str, chart_spec: ChartSpecV1, db: Session, debug: bool = False) -> dict[str, Any]:
    started_at = time.perf_counter()
    settings = get_settings()
    cache_enabled = bool(settings.CACHE_ENABLED) and not debug
    ttl_seconds = int(settings.CACHE_TTL_SECONDS)

    normalized_spec, y_metric, _, columns = _validate_histogram_spec(dataset_id, chart_spec)
    cache_key = _build_cache_key(dataset_id=dataset_id, normalized_spec=normalized_spec)
    cache = get_cache()

    if cache_enabled:
        cached_payload = cache.get(cache_key)
        if isinstance(cached_payload, dict):
            cached_meta = dict(cached_payload.get("meta", {}))
            cached_meta["cache"] = _cache_meta(
                enabled=True,
                hit=True,
                key=cache_key,
                ttl_seconds=ttl_seconds,
            )
            cached_payload["meta"] = cached_meta
            return sanitize_for_json(cached_payload)

    aggregate_filters = _to_aggregate_filters(normalized_spec.filters)
    aggregate_filters.append(AggregateFilter(column=y_metric.field, op="is_not_null"))
    where_clause, params = _build_where_clause(aggregate_filters, set(columns.keys()))
    mart = get_mart(dataset_id, normalized_spec.table)

    sample_limit = min(max(normalized_spec.limit * 50, 250), 5000)
    value_column = y_metric.alias or y_metric.field
    sql = f"""
        SELECT {_quote_identifier(y_metric.field)} AS {_quote_identifier(value_column)}
        FROM "{mart['schema']}"."{normalized_spec.table}"
        {where_clause}
        LIMIT :limit
    """
    params["limit"] = sample_limit

    statement = text(sql)
    sql_debug: str | None = None
    if debug:
        try:
            compiled = statement.compile(bind=db.get_bind(), compile_kwargs={"literal_binds": False})
            sql_debug = str(compiled)
        except Exception:
            sql_debug = sql

    try:
        rows = db.execute(statement, params).fetchall()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Histogram query failed: {exc}") from exc

    output_rows = [{value_column: row[0]} for row in rows if row and row[0] is not None]
    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response = {
        "chart_spec": normalized_spec.model_dump(mode="json"),
        "columns": [value_column],
        "rows": output_rows,
        "meta": {
            "resolver": "chartspec_v1",
            "execution_ms": elapsed_ms,
            "metric": {
                "field": y_metric.field,
                "aggregation": "distribution",
                "output_column": value_column,
            },
            "histogram": {
                "sample_size": len(output_rows),
                "source_field": y_metric.field,
            },
            "cache": _cache_meta(
                enabled=cache_enabled,
                hit=False,
                key=cache_key if cache_enabled else None,
                ttl_seconds=ttl_seconds,
            ),
        },
    }
    if debug:
        response["meta"]["debug"] = {
            "chartspec_json": normalized_spec.model_dump(mode="json"),
            "sql": sql_debug,
            "params": params,
        }
    if cache_enabled:
        cache.set(cache_key, response, ttl_seconds=ttl_seconds)
    return sanitize_for_json(response)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _build_cache_key(dataset_id: str, normalized_spec: ChartSpecV1) -> str:
    normalized_payload = normalized_spec.model_dump(mode="json", exclude_none=True)
    canonical = _canonical_json(normalized_payload)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"charts:{dataset_id}:{normalized_spec.table}:{digest}"


def _cache_meta(enabled: bool, hit: bool, key: str | None, ttl_seconds: int) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "hit": hit,
        "key": key,
        "ttl_seconds": ttl_seconds,
    }


def execute_chart_preview(dataset_id: str, chart_spec: ChartSpecV1, db: Session, debug: bool = False) -> dict[str, Any]:
    if chart_spec.chart.type == "histogram":
        return _execute_histogram_preview(dataset_id=dataset_id, chart_spec=chart_spec, db=db, debug=debug)

    started_at = time.perf_counter()
    settings = get_settings()
    cache_enabled = bool(settings.CACHE_ENABLED) and not debug
    ttl_seconds = int(settings.CACHE_TTL_SECONDS)

    resolved = resolve_chart_spec(dataset_id=dataset_id, chart_spec=chart_spec)
    cache_key = _build_cache_key(dataset_id=dataset_id, normalized_spec=resolved.normalized_spec)
    cache = get_cache()

    if cache_enabled:
        cached_payload = cache.get(cache_key)
        if isinstance(cached_payload, dict):
            cached_meta = dict(cached_payload.get("meta", {}))
            cached_meta["cache"] = _cache_meta(
                enabled=True,
                hit=True,
                key=cache_key,
                ttl_seconds=ttl_seconds,
            )
            cached_payload["meta"] = cached_meta
            return sanitize_for_json(cached_payload)

    aggregate_payload = execute_aggregate_request(
        dataset_id=dataset_id,
        request=resolved.aggregate_request,
        db=db,
        debug=debug,
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
            "cache": _cache_meta(
                enabled=cache_enabled,
                hit=False,
                key=cache_key if cache_enabled else None,
                ttl_seconds=ttl_seconds,
            ),
        },
    }
    if debug:
        aggregate_debug = aggregate_meta.get("debug", {}) if isinstance(aggregate_meta, dict) else {}
        response["meta"]["debug"] = {
            "chartspec_json": resolved.normalized_spec.model_dump(mode="json"),
            "resolved_aggregate_request_json": resolved.aggregate_request.model_dump(mode="json"),
            "sql": aggregate_debug.get("sql"),
            "params": aggregate_debug.get("params", {}),
        }
    if cache_enabled:
        cache_payload = {
            "chart_spec": response["chart_spec"],
            "columns": response["columns"],
            "rows": response["rows"],
            "meta": {
                **response["meta"],
                "cache": _cache_meta(
                    enabled=True,
                    hit=False,
                    key=cache_key,
                    ttl_seconds=ttl_seconds,
                ),
            },
        }
        cache.set(cache_key, cache_payload, ttl_seconds=ttl_seconds)
    return sanitize_for_json(response)
