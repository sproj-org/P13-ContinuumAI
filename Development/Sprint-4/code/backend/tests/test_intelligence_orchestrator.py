from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_intelligence_orchestrator.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.models.kpi_registry import KPIRegistryEntry  # noqa: E402
from app.models.strategy_bundle import (  # noqa: E402
    StrategyBundle,
    StrategyScoringModel,
    StrategyScoringWeights,
    StrategicContext,
    TargetThreshold,
)
from app.services.intelligence import orchestrator  # noqa: E402
from app.services.intelligence.specs import AnalysisRequest, PredictionPoint, PredictionSummary  # noqa: E402


def _strategy_bundle() -> StrategyBundle:
    return StrategyBundle(
        version="test",
        strategic_context=StrategicContext(
            company="ContinuumAI",
            horizon="FY26",
            north_star_metric="Revenue Growth",
            narrative="Test bundle",
        ),
        pillars=[],
        swot=None,
        targets={"total_sales": TargetThreshold(target=1000.0, direction="up")},
        decision_rules=[],
        scoring_model=StrategyScoringModel(weights=StrategyScoringWeights()),
    )


def _sales_kpi() -> KPIRegistryEntry:
    return KPIRegistryEntry(
        id="total_sales",
        display_name="Total Sales",
        description="Total net sales",
        formula="sum(net_sales)",
        marts=["gold_sales_daily"],
        required_columns=["net_sales"],
        dimensions=["region", "sales_date"],
        semantic_family="sales",
        business_concepts=["revenue", "sales"],
        metric_aliases=["net sales", "sales"],
        preferred_drill_path=["region", "store_id"],
        terminal_dimensions=["store_id"],
    )


def _profile_with_fields() -> dict[str, object]:
    return {
        "columns": [
            {"name": "sales_date", "effective_role": "temporal", "physical_type": "date"},
            {"name": "net_sales", "effective_role": "measure", "physical_type": "float"},
            {"name": "store_id", "effective_role": "dimension", "physical_type": "text"},
        ]
    }


def test_create_plan_routes_forecast_to_ml_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "_load_strategy_runtime", lambda: (_strategy_bundle(), [_sales_kpi()]))
    monkeypatch.setattr(orchestrator, "load_mart_profile", lambda dataset_id, table: _profile_with_fields())
    monkeypatch.setattr(orchestrator, "resolve_time_field", lambda profile, preferred=None: preferred or "sales_date")

    plan, matched_kpi = orchestrator.create_plan(
        AnalysisRequest(message="Forecast total sales for the next quarter", table="gold_sales_daily"),
        dataset_id="silkroute",
    )

    assert matched_kpi is not None
    assert matched_kpi.id == "total_sales"
    assert plan.primary_task == "forecast"
    assert plan.tasks[0].agent_role == "ml_agent"
    assert plan.tasks[0].prediction_spec is not None
    assert plan.tasks[0].prediction_spec.metric == "net_sales"
    assert plan.tasks[0].prediction_spec.time_field == "sales_date"


def test_create_plan_routes_segmentation_to_ml_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "_load_strategy_runtime", lambda: (_strategy_bundle(), [_sales_kpi()]))
    monkeypatch.setattr(orchestrator, "load_mart_profile", lambda dataset_id, table: _profile_with_fields())
    monkeypatch.setattr(orchestrator, "resolve_entity_field", lambda profile, preferred=None: preferred or "store_id")

    plan, _ = orchestrator.create_plan(
        AnalysisRequest(message="Segment stores by performance patterns", table="gold_sales_daily"),
        dataset_id="silkroute",
    )

    assert plan.primary_task == "segment"
    assert plan.tasks[0].agent_role == "ml_agent"
    assert plan.tasks[0].segment_spec is not None
    assert plan.tasks[0].segment_spec.entity_field == "store_id"


def test_run_analysis_request_returns_normalized_forecast_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "_load_strategy_runtime", lambda: (_strategy_bundle(), [_sales_kpi()]))
    monkeypatch.setattr(orchestrator, "load_mart_profile", lambda dataset_id, table: _profile_with_fields())
    monkeypatch.setattr(orchestrator, "resolve_time_field", lambda profile, preferred=None: preferred or "sales_date")

    def fake_run_prediction_analysis(spec, db):
        return PredictionSummary(
            mode=spec.mode,
            metric=spec.metric,
            time_field=spec.time_field,
            time_grain=spec.time_grain,
            horizon=spec.horizon,
            points=[
                PredictionPoint(label="2024-01", actual=100.0, anomaly_flag=False, is_forecast=False),
                PredictionPoint(label="2024-02", actual=112.0, anomaly_flag=False, is_forecast=False),
                PredictionPoint(label="2024-03", forecast=125.0, anomaly_flag=False, is_forecast=True),
            ],
            anomalies=[],
            projected_change_pct=0.25,
            risk_band="low",
            target_value=spec.target_value,
            target_direction=spec.target_direction,
            explanation="Forecast indicates continued growth.",
        )

    monkeypatch.setattr(orchestrator, "run_prediction_analysis", fake_run_prediction_analysis)

    response = orchestrator.run_analysis_request(
        dataset_id="silkroute",
        request=AnalysisRequest(
            task_type="forecast",
            message="Forecast total sales",
            table="gold_sales_daily",
            metric="net_sales",
            time_field="sales_date",
            horizon=2,
        ),
        db=SimpleNamespace(),
    )

    assert response.task_type == "forecast"
    assert response.agent_role == "ml_agent"
    assert response.prediction is not None
    assert response.primary_view is not None
    assert response.primary_view.chart_spec is not None
    assert response.primary_view.chart_spec.chart.type == "line"
    assert response.insight_cards
    assert any(action.action_type == "segment" for action in response.suggested_actions)
