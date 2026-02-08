"""Role-aware statistics calculator for profiled columns."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import String, case, func, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.sql.schema import Table

from services.profiling.profile_schema import Role


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _to_json_scalar(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _top_k(
    conn: Connection,
    table: Table,
    column_name: str,
    non_null_count: int,
    limit: int,
) -> List[Dict[str, Any]]:
    col = table.c[column_name]
    stmt = (
        select(func.cast(col, String).label("value"), func.count().label("count"))
        .where(col.is_not(None))
        .group_by(col)
        .order_by(func.count().desc())
        .limit(limit)
    )

    rows = conn.execute(stmt).mappings().all()
    results: List[Dict[str, Any]] = []

    for row in rows:
        count = int(row["count"] or 0)
        percent = (count / non_null_count) if non_null_count else 0.0
        results.append(
            {
                "value": str(row["value"]),
                "count": count,
                "percent": percent,
            }
        )

    return results


def _batch_numeric_aggregates(
    conn: Connection,
    table: Table,
    numeric_measure_columns: List[str],
) -> Dict[str, Dict[str, Any]]:
    if not numeric_measure_columns:
        return {}

    exprs = []
    for name in numeric_measure_columns:
        col = table.c[name]
        exprs.extend(
            [
                func.min(col).label(f"{name}__min"),
                func.max(col).label(f"{name}__max"),
                func.avg(col).label(f"{name}__mean"),
                func.stddev_samp(col).label(f"{name}__stddev"),
                func.sum(case((col == 0, 1), else_=0)).label(f"{name}__zero_count"),
            ]
        )

    stmt = select(*exprs).select_from(table)
    row = conn.execute(stmt).mappings().one()

    aggregates: Dict[str, Dict[str, Any]] = {}
    for name in numeric_measure_columns:
        aggregates[name] = {
            "min": _to_float(row.get(f"{name}__min")),
            "max": _to_float(row.get(f"{name}__max")),
            "mean": _to_float(row.get(f"{name}__mean")),
            "stddev": _to_float(row.get(f"{name}__stddev")),
            "zero_count": int(row.get(f"{name}__zero_count") or 0),
        }

    return aggregates


def _numeric_quantiles(conn: Connection, table: Table, column_name: str) -> Dict[str, float | None]:
    col = table.c[column_name]
    stmt = (
        select(
            func.percentile_cont(0.05).within_group(col).label("p05"),
            func.percentile_cont(0.50).within_group(col).label("p50"),
            func.percentile_cont(0.95).within_group(col).label("p95"),
        )
        .where(col.is_not(None))
        .select_from(table)
    )

    row = conn.execute(stmt).mappings().one()
    return {
        "p05": _to_float(row.get("p05")),
        "p50": _to_float(row.get("p50")),
        "p95": _to_float(row.get("p95")),
    }


def _datetime_stats(conn: Connection, table: Table, column_name: str, null_count: int) -> Dict[str, Any]:
    col = table.c[column_name]
    try:
        stmt = (
            select(
                func.min(col).label("min"),
                func.max(col).label("max"),
                func.count(func.distinct(func.date(col))).label("distinct_days"),
            )
            .where(col.is_not(None))
            .select_from(table)
        )
        row = conn.execute(stmt).mappings().one()
        return {
            "kind": "datetime",
            "null_count": null_count,
            "min": _to_json_scalar(row.get("min")),
            "max": _to_json_scalar(row.get("max")),
            "distinct_days": int(row.get("distinct_days") or 0),
        }
    except Exception:
        # If DATE() is not applicable, still provide min/max.
        stmt = (
            select(
                func.min(func.cast(col, String)).label("min"),
                func.max(func.cast(col, String)).label("max"),
            )
            .where(col.is_not(None))
            .select_from(table)
        )
        row = conn.execute(stmt).mappings().one()
        return {
            "kind": "datetime",
            "null_count": null_count,
            "min": _to_json_scalar(row.get("min")),
            "max": _to_json_scalar(row.get("max")),
            "distinct_days": None,
        }


def _boolean_stats(conn: Connection, table: Table, column_name: str, null_count: int) -> Dict[str, Any]:
    col = table.c[column_name]
    as_text = func.lower(func.cast(col, String))

    stmt = select(
        func.sum(case((as_text.in_(["true", "t", "1", "yes", "y"]), 1), else_=0)).label("true_count"),
        func.sum(case((as_text.in_(["false", "f", "0", "no", "n"]), 1), else_=0)).label("false_count"),
    ).select_from(table)

    row = conn.execute(stmt).mappings().one()

    return {
        "kind": "boolean",
        "true_count": int(row.get("true_count") or 0),
        "false_count": int(row.get("false_count") or 0),
        "null_count": null_count,
    }


def _text_stats(
    conn: Connection,
    table: Table,
    column: Dict[str, Any],
    top_k_limit: int,
) -> Dict[str, Any]:
    name = column["name"]
    col = table.c[name]

    len_expr = func.length(func.cast(col, String))
    stmt = (
        select(
            func.min(len_expr).label("min_len"),
            func.max(len_expr).label("max_len"),
            func.avg(len_expr).label("avg_len"),
        )
        .where(col.is_not(None))
        .select_from(table)
    )
    row = conn.execute(stmt).mappings().one()

    top_k: List[Dict[str, Any]] = []
    if column["cardinality_bucket"] == "low":
        non_null_count = max(int(column["row_count"] - column["null_count"]), 0)
        top_k = _top_k(conn, table, name, non_null_count, top_k_limit)

    return {
        "kind": "text",
        "min_len": int(row["min_len"]) if row.get("min_len") is not None else None,
        "max_len": int(row["max_len"]) if row.get("max_len") is not None else None,
        "avg_len": _to_float(row.get("avg_len")),
        "sample_values": column.get("sample_values", []),
        "top_k": top_k,
    }


def compute_role_aware_stats(
    engine: Engine,
    table: Table,
    columns: List[Dict[str, Any]],
    top_k_limit: int = 10,
) -> List[Dict[str, Any]]:
    """Compute stats based on role + datatype, not just measure columns."""
    updated_columns = [dict(col) for col in columns]

    numeric_measure_columns = [
        col["name"]
        for col in updated_columns
        if col["effective_role"] == Role.MEASURE.value and col["logical_type"] == "numeric"
    ]

    with engine.connect() as conn:
        numeric_aggregates = _batch_numeric_aggregates(
            conn=conn,
            table=table,
            numeric_measure_columns=numeric_measure_columns,
        )

        for column in updated_columns:
            role = column["effective_role"]
            name = column["name"]
            null_count = int(column["null_count"])
            distinct_count = int(column["distinct_count"])

            if role == Role.MEASURE.value and column["logical_type"] == "numeric":
                quantiles = _numeric_quantiles(conn=conn, table=table, column_name=name)
                batch = numeric_aggregates.get(name, {})
                column["stats"] = {
                    "kind": "numeric",
                    "null_count": null_count,
                    "min": batch.get("min"),
                    "max": batch.get("max"),
                    "mean": batch.get("mean"),
                    "stddev": batch.get("stddev"),
                    "p05": quantiles["p05"],
                    "p50": quantiles["p50"],
                    "p95": quantiles["p95"],
                    "zero_count": int(batch.get("zero_count") or 0),
                }
            elif role == Role.DIMENSION.value:
                non_null_count = max(int(column["row_count"] - null_count), 0)
                column["stats"] = {
                    "kind": "categorical",
                    "null_count": null_count,
                    "distinct_count": distinct_count,
                    "top_k": _top_k(conn, table, name, non_null_count, top_k_limit),
                }
            elif role == Role.ID.value:
                column["stats"] = {
                    "kind": "categorical",
                    "null_count": null_count,
                    "distinct_count": distinct_count,
                    "top_k": [],
                }
            elif role == Role.DATETIME.value:
                column["stats"] = _datetime_stats(
                    conn=conn,
                    table=table,
                    column_name=name,
                    null_count=null_count,
                )
            elif role == Role.BOOLEAN.value:
                column["stats"] = _boolean_stats(
                    conn=conn,
                    table=table,
                    column_name=name,
                    null_count=null_count,
                )
            elif role == Role.TEXT.value:
                column["stats"] = _text_stats(
                    conn=conn,
                    table=table,
                    column=column,
                    top_k_limit=top_k_limit,
                )

    return updated_columns
