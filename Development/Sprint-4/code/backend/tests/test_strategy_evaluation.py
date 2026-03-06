from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.kpi_registry import KPIRegistryEntry
from app.services.strategy import evaluator
from app.services.strategy.schema_provider import DatasetSchemaSnapshot


def test_kpi_formula_engine_computes_ratio(monkeypatch: pytest.MonkeyPatch) -> None:
    kpi = KPIRegistryEntry.model_validate(
        {
            "id": "sales_per_order",
            "description": "Sales per order",
            "formula": "sum(net_sales)/sum(order_count)",
            "marts": ["gold_sales_daily"],
            "required_columns": ["net_sales", "order_count"],
            "dimensions": [],
        }
    )
    snapshot = DatasetSchemaSnapshot(
        dataset_id="silkroute",
        available_marts={"gold_sales_daily"},
        mart_columns={"gold_sales_daily": {"net_sales", "order_count"}},
    )

    values = {
        ("sum", "net_sales"): 200.0,
        ("sum", "order_count"): 100.0,
    }

    def fake_execute_aggregation(*, aggregation, **kwargs):  # type: ignore[no-untyped-def]
        return values[(aggregation.fn, aggregation.column)]

    monkeypatch.setattr(evaluator, "_execute_aggregation", fake_execute_aggregation)

    result = evaluator.evaluate_kpi_formula(
        dataset_id="silkroute",
        kpi=kpi,
        db=SimpleNamespace(),
        schema_snapshot=snapshot,
    )
    assert result["value"] == 2.0
    assert result["provenance"]["mart"] == "gold_sales_daily"
