from __future__ import annotations

import os
import re
from types import SimpleNamespace

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_strategy_seeded_artifacts.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.models.kpi_registry import KPIRegistry
from app.models.strategy_bundle import StrategyBundle
from app.services.strategy.coverage import compute_readiness_and_coverage
from app.services.strategy.decision_signals import build_decision_surface
from app.services.strategy.evaluation import evaluate_strategy
from app.services.strategy.schema_provider import DatasetSchemaSnapshot
from app.services.strategy.storage import load_current_artifacts

_RULE_REFERENCE_RE = re.compile(r"""(?:kpi|target)\(\s*["']([^"']+)["']\s*\)""")


def _seeded_schema_snapshot(kpi_registry: KPIRegistry) -> DatasetSchemaSnapshot:
    mart_columns: dict[str, set[str]] = {}
    for kpi in kpi_registry.kpis:
        for mart in kpi.marts:
            mart_columns.setdefault(mart, set()).update(kpi.required_columns)
    return DatasetSchemaSnapshot(
        dataset_id="silkroute",
        available_marts=set(mart_columns.keys()),
        mart_columns=mart_columns,
    )


def test_seeded_artifacts_validate_and_have_expected_density() -> None:
    strategy_payload, kpi_payload, _revision = load_current_artifacts()
    strategy_bundle = StrategyBundle.model_validate(strategy_payload)
    kpi_registry = KPIRegistry.model_validate(kpi_payload)

    assert strategy_bundle.strategic_context.company == "SilkRoute Retail"
    assert len(strategy_bundle.pillars) >= 4
    assert len(kpi_registry.kpis) >= 10
    assert len(strategy_bundle.targets) >= 8
    assert len(strategy_bundle.decision_rules) >= 8


def test_seeded_target_and_rule_references_match_kpi_registry() -> None:
    strategy_payload, kpi_payload, _revision = load_current_artifacts()
    strategy_bundle = StrategyBundle.model_validate(strategy_payload)
    kpi_registry = KPIRegistry.model_validate(kpi_payload)
    known_kpis = {kpi.id for kpi in kpi_registry.kpis}

    assert set(strategy_bundle.targets.keys()).issubset(known_kpis)

    for rule in strategy_bundle.decision_rules:
        refs = {item.strip() for item in _RULE_REFERENCE_RE.findall(rule.condition) if item.strip()}
        assert refs.issubset(known_kpis)


def test_seeded_readiness_produces_notes_and_coverage_gaps() -> None:
    strategy_payload, kpi_payload, _revision = load_current_artifacts()
    strategy_bundle = StrategyBundle.model_validate(strategy_payload)
    kpi_registry = KPIRegistry.model_validate(kpi_payload)
    snapshot = _seeded_schema_snapshot(kpi_registry)
    # Keep campaign_lift intentionally unresolved to exercise readiness notes/gaps.
    if "gold_sales_daily" in snapshot.mart_columns:
        snapshot.mart_columns["gold_sales_daily"].discard("campaign_sales")
        snapshot.mart_columns["gold_sales_daily"].discard("campaign_spend")

    readiness, coverage_gaps, summaries, _flags = compute_readiness_and_coverage(
        strategy_bundle=strategy_bundle,
        kpi_registry=kpi_registry,
        schema_snapshot=snapshot,
    )

    assert 0.0 <= readiness.overall_score <= 1.0
    assert isinstance(summaries.get("readiness_notes"), list)
    assert len(summaries.get("readiness_notes", [])) >= 1
    assert any(item.kpi_id == "campaign_lift" for item in coverage_gaps)


def test_seeded_evaluation_returns_non_empty_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    strategy_payload, kpi_payload, revision = load_current_artifacts()
    kpi_registry = KPIRegistry.model_validate(kpi_payload)
    snapshot = _seeded_schema_snapshot(kpi_registry)

    monkeypatch.setattr(
        "app.services.strategy.evaluation.load_current_artifacts",
        lambda: (strategy_payload, kpi_payload, revision),
    )
    monkeypatch.setattr("app.services.strategy.evaluation.load_dataset_schema", lambda dataset_id: snapshot)
    monkeypatch.setattr(
        "app.services.strategy.evaluation.evaluate_kpi_formula",
        lambda **kwargs: {"value": 1.0, "provenance": {"source": "seeded_test"}},
    )

    result = evaluate_strategy(dataset_id="silkroute", db=SimpleNamespace())
    assert result["revision"] == revision
    assert len(result["kpis"]) >= 10


def test_seeded_decision_surface_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    strategy_payload, kpi_payload, revision = load_current_artifacts()
    kpi_registry = KPIRegistry.model_validate(kpi_payload)
    snapshot = _seeded_schema_snapshot(kpi_registry)

    monkeypatch.setattr(
        "app.services.strategy.decision_signals.load_current_artifacts",
        lambda: (strategy_payload, kpi_payload, revision),
    )
    monkeypatch.setattr("app.services.strategy.decision_signals.load_dataset_schema", lambda dataset_id: snapshot)
    monkeypatch.setattr(
        "app.services.strategy.decision_signals.evaluate_strategy",
        lambda **kwargs: {
            "dataset_id": "silkroute",
            "revision": revision,
            "kpis": [
                {"id": "net_sales_growth", "display_name": "Net Sales Growth", "value": 0.94, "target": 1.06, "status": "red"},
                {"id": "discount_rate", "display_name": "Discount Rate", "value": 0.06, "target": 0.04, "status": "yellow"},
            ],
            "triggered_rules": [
                {
                    "id": "rule_growth_guardrail",
                    "condition": 'kpi("net_sales_growth") < target("net_sales_growth")',
                    "action": "Escalate growth recovery plan",
                    "severity": "block",
                    "affected_kpis": ["net_sales_growth"],
                }
            ],
            "evaluation_time": "2026-03-06T00:00:00Z",
        },
    )

    result = build_decision_surface(dataset_id="silkroute", db=SimpleNamespace())
    assert result["revision"] == revision
    assert len(result["decision_signals"]) >= 2
    assert len(result["recommendations"]) >= 1
    assert result["executive_summary"]["narrative"]
