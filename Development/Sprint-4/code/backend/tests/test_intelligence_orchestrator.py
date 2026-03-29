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
from app.services.intelligence.specs import (  # noqa: E402
    AnalysisContextSpec,
    AnalysisRequest,
    PredictionPoint,
    PredictionSummary,
    SemanticContextSpec,
    StrategyContextSpec,
)


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
    assert plan.tasks[0].prediction_spec.metric == "total_sales"
    assert plan.tasks[0].prediction_spec.metric_source == "formula"
    assert plan.tasks[0].prediction_spec.formula == "sum(net_sales)"
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


def test_create_plan_uses_strategy_analysis_context_for_prediction_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "_load_strategy_runtime", lambda: (_strategy_bundle(), [_sales_kpi()]))
    monkeypatch.setattr(orchestrator, "load_mart_profile", lambda dataset_id, table: _profile_with_fields())
    monkeypatch.setattr(orchestrator, "resolve_time_field", lambda profile, preferred=None: "sales_date")

    plan, matched_kpi = orchestrator.create_plan(
        AnalysisRequest(
            task_type="forecast",
            analysis_context=AnalysisContextSpec(
                source="strategy",
                table="gold_sales_daily",
                semantic=SemanticContextSpec(
                    matched_kpi_id="total_sales",
                    matched_kpi_label="Total Sales",
                    required_columns=["net_sales"],
                    metric_field_hint="net_sales",
                    time_field_hint="sales_date",
                ),
                strategy=StrategyContextSpec(target_value=1200.0, target_direction="up"),
            ),
        ),
        dataset_id="silkroute",
    )

    assert matched_kpi is not None
    assert plan.analysis_context is not None
    assert plan.analysis_context.source == "strategy"
    assert plan.tasks[0].prediction_spec is not None
    assert plan.tasks[0].prediction_spec.metric == "total_sales"
    assert plan.tasks[0].prediction_spec.metric_source == "formula"
    assert plan.tasks[0].prediction_spec.display_label == "Total Sales"
    assert plan.tasks[0].prediction_spec.target_value == 1200.0


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
    assert response.primary_view.chart_spec is None
    assert response.insight_cards
    assert any(action.action_type == "segment" for action in response.suggested_actions)


def test_run_analysis_request_strategy_risk_handles_human_kpi_label_without_chart_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    growth_kpi = KPIRegistryEntry(
        id="net_sales_growth",
        display_name="Net Sales Growth",
        description="Net sales growth",
        formula="sum(net_sales)",
        marts=["gold_sales_daily"],
        required_columns=["net_sales"],
        dimensions=["region", "sales_date"],
        semantic_family="revenue",
        business_concepts=["revenue", "growth"],
        metric_aliases=["net sales growth"],
        preferred_drill_path=["region", "store_id"],
        terminal_dimensions=["store_id"],
    )
    bundle = StrategyBundle(
        version="test",
        strategic_context=_strategy_bundle().strategic_context,
        pillars=[],
        swot=None,
        targets={"net_sales_growth": TargetThreshold(target=25.0, direction="up", horizon="FY26")},
        decision_rules=[],
        scoring_model=StrategyScoringModel(weights=StrategyScoringWeights()),
    )
    monkeypatch.setattr(orchestrator, "_load_strategy_runtime", lambda: (bundle, [growth_kpi]))
    monkeypatch.setattr(orchestrator, "evaluate_kpi_formula", lambda **kwargs: {"value": 14.0})

    def fake_prediction(spec, db):
        return PredictionSummary(
            mode="risk",
            metric="net_sales_growth",
            display_label="Net Sales Growth",
            metric_source="formula",
            formula="sum(net_sales)",
            time_field="sales_date",
            time_grain="month",
            horizon=2,
            points=[
                PredictionPoint(label="2024-01", actual=10.0, anomaly_flag=False, is_forecast=False),
                PredictionPoint(label="2024-02", actual=14.0, anomaly_flag=False, is_forecast=False),
                PredictionPoint(label="2024-03", forecast=18.0, lower=16.0, upper=20.0, anomaly_flag=False, is_forecast=True),
                PredictionPoint(label="2024-04", forecast=22.0, lower=20.0, upper=24.0, anomaly_flag=False, is_forecast=True),
            ],
            anomalies=[],
            observed_points=2,
            historical_start="2024-01",
            historical_end="2024-02",
            projected_change_pct=0.57,
            risk_band="medium",
            target_value=25.0,
            target_direction="up",
            confidence_score=0.62,
            explanation="Projected growth remains below the FY26 target.",
        )

    monkeypatch.setattr(orchestrator, "run_prediction_analysis", fake_prediction)

    response = orchestrator.run_analysis_request(
        dataset_id="silkroute",
        request=AnalysisRequest(
            task_type="strategy_risk",
            kpi_id="net_sales_growth",
            analysis_context=AnalysisContextSpec(
                source="strategy",
                semantic=SemanticContextSpec(
                    matched_kpi_id="net_sales_growth",
                    matched_kpi_label="Net Sales Growth",
                ),
                strategy=StrategyContextSpec(
                    target_value=25.0,
                    target_direction="up",
                    target_horizon="FY26",
                    triggered_rules=["Escalate if growth stays below plan."],
                    triggered_rule_actions=["Review underperforming regions"],
                ),
            ),
        ),
        db=SimpleNamespace(),
    )

    assert response.task_type == "strategy_risk"
    assert response.strategy is not None
    assert response.strategy.kpi_label == "Net Sales Growth"
    assert response.strategy.target_horizon == "FY26"
    assert response.primary_view is not None
    assert response.primary_view.chart_spec is None
    assert response.strategy.forecast_basis is not None
    assert response.plan_spec.analysis_context is not None
    assert response.plan_spec.analysis_context.source == "strategy"


def test_create_plan_strategy_risk_builds_multistep_dependency_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "_load_strategy_runtime", lambda: (_strategy_bundle(), [_sales_kpi()]))
    monkeypatch.setattr(orchestrator, "load_mart_profile", lambda dataset_id, table: _profile_with_fields())
    monkeypatch.setattr(orchestrator, "resolve_time_field", lambda profile, preferred=None: "sales_date")

    plan, matched_kpi = orchestrator.create_plan(
        AnalysisRequest(
            task_type="strategy_risk",
            kpi_id="total_sales",
            analysis_context=AnalysisContextSpec(
                source="strategy",
                table="gold_sales_daily",
                semantic=SemanticContextSpec(
                    matched_kpi_id="total_sales",
                    matched_kpi_label="Total Sales",
                    required_columns=["net_sales"],
                    metric_field_hint="net_sales",
                    time_field_hint="sales_date",
                ),
                strategy=StrategyContextSpec(target_value=1000.0, target_direction="up"),
            ),
        ),
        dataset_id="silkroute",
    )

    assert matched_kpi is not None
    assert plan.primary_task == "strategy_risk"
    assert [task.agent_role for task in plan.tasks] == ["ml_agent", "strategy_agent", "insight_agent"]
    assert plan.tasks[1].depends_on_task_ids == [plan.tasks[0].task_id]
    assert plan.tasks[2].depends_on_task_ids == [plan.tasks[1].task_id]
    assert plan.tasks[0].prediction_spec is not None
    assert plan.tasks[0].prediction_spec.metric_source == "formula"
    assert plan.tasks[0].prediction_spec.formula == "sum(net_sales)"


def test_run_analysis_request_strategy_risk_keeps_working_without_prediction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "_load_strategy_runtime", lambda: (_strategy_bundle(), [_sales_kpi()]))
    monkeypatch.setattr(orchestrator, "load_mart_profile", lambda dataset_id, table: _profile_with_fields())
    monkeypatch.setattr(orchestrator, "resolve_time_field", lambda profile, preferred=None: "sales_date")
    monkeypatch.setattr(orchestrator, "evaluate_kpi_formula", lambda **kwargs: {"value": 820.0})

    def fail_prediction(spec, db):
        raise orchestrator.HTTPException(status_code=404, detail="No rows are available for predictive analysis")

    monkeypatch.setattr(orchestrator, "run_prediction_analysis", fail_prediction)

    response = orchestrator.run_analysis_request(
        dataset_id="silkroute",
        request=AnalysisRequest(
            task_type="strategy_risk",
            kpi_id="total_sales",
            analysis_context=AnalysisContextSpec(
                source="strategy",
                table="gold_sales_daily",
                semantic=SemanticContextSpec(
                    matched_kpi_id="total_sales",
                    matched_kpi_label="Total Sales",
                    required_columns=["net_sales"],
                    metric_field_hint="net_sales",
                    time_field_hint="sales_date",
                ),
                strategy=StrategyContextSpec(target_value=1000.0, target_direction="up", target_horizon="FY26"),
            ),
        ),
        db=SimpleNamespace(),
    )

    assert response.strategy is not None
    assert response.strategy.current_value == 820.0
    assert response.strategy.projected_value is None
    assert response.strategy.risk_band == "unknown"
    assert response.primary_view is None
    assert isinstance(response.meta.get("execution_trace"), list)
