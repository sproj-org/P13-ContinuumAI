from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_result_answers.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.services.intelligence.result_answers import build_analysis_answer_evidence
from app.services.intelligence.specs import (
    AnalysisResponse,
    PlanSpec,
    PredictionPoint,
    PredictionSummary,
    SegmentProfile,
    SegmentSummary,
    StrategyRiskSummary,
)


def test_build_analysis_answer_evidence_includes_segment_extremes() -> None:
    analysis = AnalysisResponse(
        task_type="segment",
        agent_role="ml_agent",
        plan_spec=PlanSpec(
            dataset_id="silkroute",
            table="gold_customer_360",
            user_message="Segment customers",
            primary_task="segment",
            route_reason="Segment follow-up",
            tasks=[],
            suggested_follow_ups=[],
        ),
        segmentation=SegmentSummary(
            entity_field="customer_id",
            cluster_count=3,
            profiles=[
                SegmentProfile(
                    cluster_id=0,
                    label="High value loyalists",
                    entity_count=18,
                    centroid={"net_sales": 900.0, "margin_pct": 0.42},
                    metric_highlights=["high net sales", "strong margin"],
                ),
                SegmentProfile(
                    cluster_id=1,
                    label="Broad middle",
                    entity_count=64,
                    centroid={"net_sales": 420.0, "margin_pct": 0.21},
                    metric_highlights=["mid sales", "balanced mix"],
                ),
                SegmentProfile(
                    cluster_id=2,
                    label="Low value attrition risk",
                    entity_count=12,
                    centroid={"net_sales": 85.0, "margin_pct": 0.08},
                    metric_highlights=["low sales", "thin margin"],
                ),
            ],
            comparison_highlights=["Cluster 0 materially outperforms the rest on sales and margin."],
        ),
        suggested_actions=[],
        meta={},
    )

    evidence = build_analysis_answer_evidence(analysis)

    assert evidence["segmentation"]["primary_metric"] == "net_sales"
    assert evidence["segmentation"]["strongest_cluster"]["cluster_id"] == 0
    assert evidence["segmentation"]["weakest_cluster"]["cluster_id"] == 2
    assert evidence["segmentation"]["largest_cluster"]["cluster_id"] == 1


def test_build_analysis_answer_evidence_includes_forecast_and_risk_context() -> None:
    analysis = AnalysisResponse(
        task_type="strategy_risk",
        agent_role="strategy_agent",
        plan_spec=PlanSpec(
            dataset_id="silkroute",
            table="gold_sales_daily",
            user_message="Why is this KPI at risk?",
            primary_task="strategy_risk",
            route_reason="Risk follow-up",
            tasks=[],
            suggested_follow_ups=[],
        ),
        prediction=PredictionSummary(
            mode="forecast",
            metric="net_sales",
            display_label="Net Sales",
            time_field="sales_date",
            time_grain="month",
            observed_points=2,
            horizon=2,
            points=[
                PredictionPoint(label="2025-01", actual=100.0, anomaly_flag=False, is_forecast=False),
                PredictionPoint(label="2025-02", actual=92.0, anomaly_flag=False, is_forecast=False),
                PredictionPoint(label="2025-03", forecast=88.0, anomaly_flag=False, is_forecast=True),
                PredictionPoint(label="2025-04", forecast=86.0, anomaly_flag=False, is_forecast=True),
            ],
            target_value=95.0,
            risk_band="medium",
            confidence_score=0.58,
            explanation="The recent trend remains below the target trajectory.",
        ),
        strategy=StrategyRiskSummary(
            kpi_id="net_sales_growth",
            kpi_label="Net Sales Growth",
            current_value=92.0,
            projected_value=86.0,
            target_value=95.0,
            variance_to_target=-9.0,
            risk_band="medium",
            confidence_score=0.58,
            target_horizon="quarter",
            forecast_basis="Recent sales trend",
            explanation="Recent growth remains below the target path.",
            recommended_actions=["Compare the weakest region against the strongest."],
            supporting_details=["South region is trailing plan."],
        ),
        suggested_actions=[],
        meta={},
    )

    evidence = build_analysis_answer_evidence(analysis)

    assert evidence["forecast"]["observed_window"]["delta"] == -8.0
    assert evidence["forecast"]["target_gap"] == -9.0
    assert evidence["risk"]["risk_band"] == "medium"
    assert evidence["risk"]["recommended_actions"][0] == "Compare the weakest region against the strongest."
