"""
ChartSpec Resolver — converts a ChartSpec into an AggregateRequest.

This is a pure transformation layer with no DB or I/O access.
The resolver extracts dimensions from encoding.x, metrics from encoding.y,
and passes through filters, sort, and limit.
"""

from app.schemas.chart_spec import (
    ChartSpec,
    AggregateRequest,
    Metric,
    Filter,
    SortSpec,
)


def resolve_chart_spec(spec: ChartSpec) -> AggregateRequest:
    """
    Convert a ChartSpec into an AggregateRequest that the engine can execute.

    Mapping rules:
      - encoding.x.field → dimensions[0]
      - encoding.y[]     → metrics[] (field, agg, alias)
      - filters          → filters (passed through)
      - sort             → sort (passed through)
      - limit            → limit (capped at 500)
    """
    # Extract dimension from x-axis encoding
    dimensions = [spec.encoding.x.field]

    # Extract metrics from y-axis encoding(s)
    metrics = [
        Metric(
            field=m.field,
            aggregation=m.agg,
            alias=m.alias or f"{m.agg}_{m.field}",
        )
        for m in spec.encoding.y
    ]

    # Map filters
    filters = [Filter(field=f.field, op=f.op, value=f.value) for f in spec.filters]

    # Pass through sort specs
    sort = [SortSpec(field=s.field, dir=s.dir) for s in spec.sort]

    return AggregateRequest(
        table=spec.table,
        dimensions=dimensions,
        metrics=metrics,
        filters=filters,
        limit=min(spec.limit, 500),
        sort=sort,
    )
