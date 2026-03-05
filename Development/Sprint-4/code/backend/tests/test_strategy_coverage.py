from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.kpi_registry import KPIRegistry
from app.models.strategy_bundle import StrategyBundle
from app.services.strategy.coverage import compute_readiness_and_coverage
from app.services.strategy.schema_provider import DatasetSchemaSnapshot, load_dataset_schema
from app.services.strategy import schema_provider


def _sample_strategy_bundle() -> StrategyBundle:
    return StrategyBundle.model_validate(
        {
            "schema_version": 1,
            "version": "1.0.0",
            "strategic_context": {
                "company": "Demo Company",
                "horizon": "12 months",
                "north_star_metric": "net_sales",
            },
            "pillars": [{"id": "growth", "description": "Grow revenue"}],
            "targets": {},
            "decision_rules": [
                {
                    "id": "rule_1",
                    "condition": "sales_growth > 0.1",
                    "action": "prioritize growth investments",
                    "severity": "warn",
                }
            ],
            "scoring_model": {
                "weights": {
                    "kpi_coverage": 0.4,
                    "rule_readiness": 0.2,
                    "hierarchy_readiness": 0.2,
                    "data_readiness": 0.2,
                }
            },
        }
    )


def test_schema_provider_parses_columns_and_handles_missing_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "sales_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "table_name": "gold_sales_daily",
                "columns": [
                    {"name": "net_sales"},
                    {"name": "region"},
                    {"name": "sales_date"},
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(schema_provider, "OUT_DIR", tmp_path)
    monkeypatch.setattr(schema_provider, "is_supported_dataset", lambda dataset_id: dataset_id == "silkroute")
    monkeypatch.setattr(
        schema_provider,
        "list_marts",
        lambda dataset_id: [
            {"id": "gold_sales_daily", "profile_file": "sales_profile.json"},
            {"id": "gold_customer_360", "profile_file": "missing_profile.json"},
        ],
    )

    snapshot = load_dataset_schema("silkroute")
    assert "gold_sales_daily" in snapshot.available_marts
    assert snapshot.mart_columns["gold_sales_daily"] == {"net_sales", "region", "sales_date"}
    assert snapshot.unavailable_marts["gold_customer_360"] == "missing_profile_json"


def test_coverage_reports_missing_dependencies() -> None:
    strategy_bundle = _sample_strategy_bundle()
    kpi_registry = KPIRegistry.model_validate(
        {
            "schema_version": 1,
            "version": "1.0.0",
            "kpis": [
                {
                    "id": "sales_growth",
                    "description": "Sales growth",
                    "formula": "sum(net_sales)",
                    "marts": ["gold_sales_daily"],
                    "required_columns": ["net_sales", "region", "missing_col"],
                }
            ],
        }
    )
    snapshot = DatasetSchemaSnapshot(
        dataset_id="silkroute",
        available_marts={"gold_sales_daily"},
        mart_columns={"gold_sales_daily": {"net_sales", "region"}},
    )

    readiness, gaps, summaries = compute_readiness_and_coverage(
        strategy_bundle=strategy_bundle,
        kpi_registry=kpi_registry,
        schema_snapshot=snapshot,
    )

    assert len(gaps) == 1
    assert gaps[0].kpi_id == "sales_growth"
    assert readiness.kpi_coverage < 1.0
    assert summaries["missing_columns_total"] == 1
