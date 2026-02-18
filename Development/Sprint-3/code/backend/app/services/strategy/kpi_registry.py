"""Minimal KPI registry foundation for single-mart chart generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException

from app.core.mart_registry import get_mart_ids, is_supported_dataset
from app.services.charts.models import ChartSpecV1


@dataclass(frozen=True)
class KPIEntry:
    id: str
    label: str
    description: str
    table: str
    default_metric: dict[str, Any]
    default_dimension: str
    default_filters: list[dict[str, Any]] = field(default_factory=list)


KPI_REGISTRY: list[KPIEntry] = [
    KPIEntry(
        id="sales_by_region",
        label="Sales by Region",
        description="Track total net sales grouped by region.",
        table="gold_sales_daily",
        default_metric={"field": "net_sales", "aggregation": "sum", "alias": "total_net_sales"},
        default_dimension="region",
    ),
    KPIEntry(
        id="sales_by_channel",
        label="Sales by Channel",
        description="Compare gross sales performance across channels.",
        table="gold_sales_daily",
        default_metric={"field": "gross_sales", "aggregation": "sum", "alias": "total_gross_sales"},
        default_dimension="channel_type",
    ),
    KPIEntry(
        id="store_performance",
        label="Store Performance",
        description="Monitor store-level net sales contribution.",
        table="gold_store_360",
        default_metric={"field": "net_sales", "aggregation": "sum", "alias": "total_net_sales"},
        default_dimension="store_type",
    ),
    KPIEntry(
        id="customer_segment_revenue",
        label="Customer Segment Revenue",
        description="Measure sales contribution by customer segment.",
        table="gold_customer_360",
        default_metric={"field": "gross_sales", "aggregation": "sum", "alias": "segment_gross_sales"},
        default_dimension="segment",
    ),
]


def _dataset_kpis(dataset_id: str) -> list[KPIEntry]:
    if not is_supported_dataset(dataset_id):
        raise HTTPException(status_code=404, detail=f"Unknown dataset_id '{dataset_id}'")

    supported_marts = set(get_mart_ids(dataset_id))
    return [entry for entry in KPI_REGISTRY if entry.table in supported_marts]


def list_kpis(dataset_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in _dataset_kpis(dataset_id):
        items.append(
            {
                "id": entry.id,
                "label": entry.label,
                "description": entry.description,
                "table": entry.table,
                "default_metric": dict(entry.default_metric),
                "default_dimension": entry.default_dimension,
                "default_filters": [dict(item) for item in entry.default_filters],
            }
        )
    return items


def lookup_kpi(dataset_id: str, kpi_id: str) -> dict[str, Any]:
    for entry in _dataset_kpis(dataset_id):
        if entry.id == kpi_id:
            return {
                "id": entry.id,
                "label": entry.label,
                "description": entry.description,
                "table": entry.table,
                "exec_hint": {
                    "table": entry.table,
                    "default_dimension": entry.default_dimension,
                    "default_metric": dict(entry.default_metric),
                    "default_filters": [dict(item) for item in entry.default_filters],
                },
            }
    raise HTTPException(status_code=404, detail=f"KPI '{kpi_id}' is not registered for dataset '{dataset_id}'")


def kpi_to_chartspec(
    dataset_id: str,
    kpi_id: str,
    overrides: dict[str, Any] | None = None,
) -> ChartSpecV1:
    overrides = overrides or {}
    kpi = lookup_kpi(dataset_id=dataset_id, kpi_id=kpi_id)
    hint = kpi["exec_hint"]

    table = str(overrides.get("table", hint["table"]))
    dimension = str(overrides.get("dimension", hint["default_dimension"]))
    metric = dict(hint["default_metric"])
    metric_override = overrides.get("metric")
    if isinstance(metric_override, dict):
        metric.update(metric_override)

    filters = overrides.get("filters", hint["default_filters"])
    limit = int(overrides.get("limit", 20))
    chart_type = str(overrides.get("chart_type", "bar"))

    return ChartSpecV1(
        version="v1",
        dataset_id=dataset_id,
        table=table,
        chart={"type": chart_type},
        encoding={
            "x": {"field": dimension},
            "y": [metric],
        },
        filters=filters,
        sort=[{"field": metric.get("alias", "agg_value"), "direction": "desc"}],
        limit=limit,
    )
