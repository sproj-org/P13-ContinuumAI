"""
Query API — aggregate endpoint.

POST /api/datasets/{dataset_id}/query/aggregate

Accepts a ChartSpec, resolves it into an AggregateRequest,
validates against profile metadata, builds safe SQL,
executes, and returns an AggregateResponse.
"""

import time
from decimal import Decimal
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.chart_spec import ChartSpec, AggregateResponse, ResponseMeta
from app.engine.resolver import resolve_chart_spec
from app.engine.query_builder import build_aggregate_query

router = APIRouter(prefix="/datasets", tags=["query"])


def _serialize_value(val):
    """Convert database values to JSON-serializable types."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    return val


@router.post("/{dataset_id}/query/aggregate", response_model=AggregateResponse)
def execute_aggregate(
    dataset_id: str,
    spec: ChartSpec,
    db: Session = Depends(get_db),
):
    """
    Execute an aggregate query from a ChartSpec.

    Pipeline:
      1. Resolve  — ChartSpec → AggregateRequest (with Pydantic validation)
      2. Build    — AggregateRequest → parameterised SQL
      3. Execute  — run query
      4. Format   — rows → AggregateResponse
    """
    # Ensure dataset_id in the URL matches the spec (optional guard)
    if spec.dataset_id and spec.dataset_id != dataset_id:
        raise HTTPException(
            status_code=400,
            detail=f"URL dataset_id '{dataset_id}' does not match spec dataset_id '{spec.dataset_id}'.",
        )

    # 1. Resolve (Pydantic auto-validates via model_validator)
    try:
        agg_request = resolve_chart_spec(spec)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Validation failed: {str(e)}",
        )

    # 2. Build query
    try:
        query, params = build_aggregate_query(agg_request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Query build error: {str(e)}")

    # 3. Execute
    start = time.perf_counter()
    try:
        result = db.execute(query, params)
        rows_raw = result.fetchall()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {str(e)}",
        )
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    # 4. Format response
    # Build column names list: dimensions + metric aliases
    columns: list[str] = list(agg_request.dimensions)
    for m in agg_request.metrics:
        columns.append(m.alias or f"{m.aggregation}_{m.field}")

    rows = [[_serialize_value(cell) for cell in row] for row in rows_raw]

    return AggregateResponse(
        columns=columns,
        rows=rows,
        meta=ResponseMeta(query_ms=elapsed_ms),
    )
