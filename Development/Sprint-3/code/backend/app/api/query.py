"""
Query API — aggregate endpoint.

POST /api/datasets/{dataset_id}/query/aggregate

Accepts a ChartSpec, resolves it into an AggregateRequest,
validates against profile metadata, builds safe SQL,
executes, and returns an AggregateResponse.

Includes Redis caching for improved performance on repeated queries.
"""

import time
from decimal import Decimal
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.chart_spec import ChartSpec, AggregateResponse, ResponseMeta, CacheMeta
from app.engine.resolver import resolve_chart_spec
from app.engine.query_builder import build_aggregate_query
from app.core.cache import get_cached, set_cached
from app.core.config import get_settings

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
      1. Cache Check — try to retrieve cached result
      2. Resolve     — ChartSpec → AggregateRequest (with Pydantic validation)
      3. Build       — AggregateRequest → parameterised SQL
      4. Execute     — run query
      5. Format      — rows → AggregateResponse
      6. Cache Store — save result for future requests
    """
    settings = get_settings()

    # Ensure dataset_id in the URL matches the spec (optional guard)
    if spec.dataset_id and spec.dataset_id != dataset_id:
        raise HTTPException(
            status_code=400,
            detail=f"URL dataset_id '{dataset_id}' does not match spec dataset_id '{spec.dataset_id}'.",
        )

    # 1. Check cache
    cache_key = spec.cache_key()
    cached_data = get_cached(cache_key)

    if cached_data is not None:
        # Cache hit - reconstruct response
        cached_data["meta"]["cache"] = CacheMeta(
            hit=True, key=cache_key, ttl_seconds=settings.CACHE_TTL_SECONDS
        ).model_dump()
        print("Cache hit for key:", cache_key)

        return AggregateResponse(**cached_data)

    # Cache miss - proceed with query execution
    # 2. Resolve (Pydantic auto-validates via model_validator)
    try:
        agg_request = resolve_chart_spec(spec)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Validation failed: {str(e)}",
        )

    # 3. Build query
    try:
        query, params = build_aggregate_query(agg_request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Query build error: {str(e)}")

    # 4. Execute
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

    # 5. Format response
    # Build column names list: dimensions + metric aliases
    columns: list[str] = list(agg_request.dimensions)
    for m in agg_request.metrics:
        columns.append(m.alias or f"{m.aggregation}_{m.field}")

    rows = [[_serialize_value(cell) for cell in row] for row in rows_raw]

    # 6. Store in cache (exclude meta from cache to save space)
    cache_data = {"columns": columns, "rows": rows, "meta": {"query_ms": elapsed_ms}}
    set_cached(cache_key, cache_data, ttl=settings.CACHE_TTL_SECONDS)

    # Return response with cache metadata
    return AggregateResponse(
        columns=columns,
        rows=rows,
        meta=ResponseMeta(
            query_ms=elapsed_ms,
            cache=CacheMeta(
                hit=False, key=cache_key, ttl_seconds=settings.CACHE_TTL_SECONDS
            ),
        ),
    )
