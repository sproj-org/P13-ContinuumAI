from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.kpi_registry import KPIRegistryEntry
from app.services.strategy import evaluation
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


def test_strategy_evaluation_target_status_and_missing_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    strategy_payload = {
        "schema_version": 1,
        "version": "1.0.0",
        "strategic_context": {
            "company": "Demo",
            "horizon": "12m",
            "north_star_metric": "sales_growth",
        },
        "pillars": [{"id": "growth", "description": "Growth"}],
        "swot": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
        "targets": {
            "sales_growth": {
                "target": 0.1,
                "yellow_threshold": 0.06,
                "red_threshold": 0.03,
                "direction": "up",
            }
        },
        "decision_rules": [],
        "scoring_model": {
            "weights": {
                "kpi_coverage": 0.4,
                "rule_readiness": 0.2,
                "hierarchy_readiness": 0.2,
                "data_readiness": 0.2,
            }
        },
    }
    kpi_payload = {
        "schema_version": 1,
        "version": "1.0.0",
        "kpis": [
            {
                "id": "sales_growth",
                "description": "Sales growth",
                "formula": "sum(net_sales)/sum(order_count)",
                "marts": ["gold_sales_daily"],
                "required_columns": ["net_sales", "order_count"],
                "dimensions": [],
            },
            {
                "id": "returns_rate",
                "description": "Returns rate",
                "formula": "sum(return_amount)/sum(net_sales)",
                "marts": ["gold_sales_daily"],
                "required_columns": ["return_amount", "net_sales"],
                "dimensions": [],
            },
        ],
    }
    snapshot = DatasetSchemaSnapshot(
        dataset_id="silkroute",
        available_marts={"gold_sales_daily"},
        mart_columns={"gold_sales_daily": {"net_sales", "order_count"}},
    )

    monkeypatch.setattr(evaluation, "load_current_artifacts", lambda: (strategy_payload, kpi_payload, "r0007"))
    monkeypatch.setattr(evaluation, "load_dataset_schema", lambda dataset_id: snapshot)

    def fake_formula_eval(*, kpi, **kwargs):  # type: ignore[no-untyped-def]
        if kpi.id == "sales_growth":
            return {"value": 0.08, "provenance": {"source": "mock"}}
        return {"value": None, "provenance": {"errors": ["missing dependencies"]}}

    monkeypatch.setattr(evaluation, "evaluate_kpi_formula", fake_formula_eval)

    result = evaluation.evaluate_strategy(dataset_id="silkroute", db=SimpleNamespace())
    assert result["revision"] == "r0007"
    assert len(result["kpis"]) == 2

    sales_row = next(item for item in result["kpis"] if item["id"] == "sales_growth")
    assert sales_row["status"] == "yellow"
    assert sales_row["target"] == 0.1
    assert sales_row["variance"] == pytest.approx(-0.02)

    returns_row = next(item for item in result["kpis"] if item["id"] == "returns_rate")
    assert returns_row["status"] == "unavailable"
    assert returns_row["value"] is None
