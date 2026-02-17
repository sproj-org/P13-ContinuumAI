"""
Query Builder — safe SQL generation from a validated AggregateRequest.

This is the critical security boundary.  Rules:
  - Column / table identifiers are validated against the profile whitelist
    by the validator BEFORE reaching this module, then double-quoted.
  - All *values* (filter values, limit) are passed as bound parameters.
  - No string concatenation of user-supplied values into the SQL text.
"""

import re
from typing import Any

from sqlalchemy import text

from app.schemas.chart_spec import AggregateRequest, Filter, SortSpec
from app.services.profile_service import MARTS_SCHEMA


def _quote_ident(name: str) -> str:
    """
    Double-quote a SQL identifier.
    The identifier is already validated against the profile whitelist,
    but we still quote it to handle reserved words.
    """
    # Extra safety: reject anything suspicious
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        raise ValueError(f"Unsafe identifier rejected: {name}")
    return f'"{name}"'


def _build_filter_clause(
    filters: list[Filter],
    params: dict[str, Any],
    param_counter: list[int],
) -> str:
    """
    Build a WHERE clause string and populate bound parameters.
    Returns an empty string if there are no filters.
    """
    if not filters:
        return ""

    clauses: list[str] = []
    for f in filters:
        col = _quote_ident(f.field)
        idx = param_counter[0]

        if f.op == "between":
            # value must be a list of two elements
            if not isinstance(f.value, (list, tuple)) or len(f.value) != 2:
                raise ValueError(
                    f"'between' filter for '{f.field}' requires a list of exactly 2 values."
                )
            p_lo = f"p{idx}"
            p_hi = f"p{idx + 1}"
            clauses.append(f"{col} BETWEEN :{p_lo} AND :{p_hi}")
            params[p_lo] = f.value[0]
            params[p_hi] = f.value[1]
            param_counter[0] = idx + 2

        elif f.op == "in":
            if not isinstance(f.value, (list, tuple)):
                raise ValueError(
                    f"'in' filter for '{f.field}' requires a list of values."
                )
            placeholders = []
            for i, v in enumerate(f.value):
                p_name = f"p{idx + i}"
                placeholders.append(f":{p_name}")
                params[p_name] = v
            param_counter[0] = idx + len(f.value)
            clauses.append(f"{col} IN ({', '.join(placeholders)})")

        elif f.op == "contains":
            p_name = f"p{idx}"
            clauses.append(f"{col} ILIKE :{p_name}")
            params[p_name] = f"%{f.value}%"
            param_counter[0] = idx + 1

        else:
            # Simple comparison: =, !=, <, >, <=, >=
            sql_op = f.op
            p_name = f"p{idx}"
            clauses.append(f"{col} {sql_op} :{p_name}")
            params[p_name] = f.value
            param_counter[0] = idx + 1

    return "WHERE " + " AND ".join(clauses)


def build_aggregate_query(
    request: AggregateRequest,
    schema: str = MARTS_SCHEMA,
) -> tuple[Any, dict[str, Any]]:
    """
    Build a parameterized aggregate SQL query from a validated AggregateRequest.

    Returns:
        (sqlalchemy text clause, dict of bound parameters)
    """
    params: dict[str, Any] = {}
    param_counter = [0]  # mutable counter for param naming

    # --- SELECT clause ---
    select_parts: list[str] = []

    # Dimensions
    for dim in request.dimensions:
        select_parts.append(f"CAST({_quote_ident(dim)} AS TEXT) AS {_quote_ident(dim)}")

    # Metrics
    metric_aliases: list[str] = []
    for m in request.metrics:
        agg_fn = m.aggregation.upper()
        alias = m.alias or f"{m.aggregation}_{m.field}"
        select_parts.append(
            f"{agg_fn}({_quote_ident(m.field)}) AS {_quote_ident(alias)}"
        )
        metric_aliases.append(alias)

    select_clause = ", ".join(select_parts)

    # --- FROM clause ---
    from_clause = f"{schema}.{_quote_ident(request.table)}"

    # --- WHERE clause ---
    where_clause = _build_filter_clause(request.filters, params, param_counter)

    # --- GROUP BY clause ---
    group_by_clause = ""
    if request.dimensions:
        group_by_parts = [_quote_ident(d) for d in request.dimensions]
        group_by_clause = f'GROUP BY {", ".join(group_by_parts)}'

    # --- ORDER BY clause ---
    order_by_clause = ""
    if request.sort:
        order_parts: list[str] = []
        for s in request.sort:
            direction = s.dir.upper()
            # Sort field can be a metric alias or a column name
            order_parts.append(f"{_quote_ident(s.field)} {direction}")
        order_by_clause = f'ORDER BY {", ".join(order_parts)}'
    elif metric_aliases:
        # Default: order by first metric descending
        order_by_clause = f"ORDER BY {_quote_ident(metric_aliases[0])} DESC"

    # --- LIMIT ---
    params["query_limit"] = min(request.limit, 500)

    # --- Assemble ---
    sql = f"""
        SELECT {select_clause}
        FROM {from_clause}
        {where_clause}
        {group_by_clause}
        {order_by_clause}
        LIMIT :query_limit
    """.strip()

    return text(sql), params
