"""Grounded insight-card generation for normalized analysis outputs."""

from __future__ import annotations

from typing import Any

from app.services.intelligence.specs import (
    InsightCard,
    PredictionSummary,
    QuerySpec,
    SegmentSummary,
    StrategyRiskSummary,
    SuggestedAction,
)


def build_prediction_insights(prediction: PredictionSummary, *, kpi_label: str | None = None) -> list[InsightCard]:
    cards: list[InsightCard] = []
    label = kpi_label or prediction.display_label or prediction.metric
    if prediction.projected_change_pct is not None:
        direction = "up" if prediction.projected_change_pct >= 0 else "down"
        cards.append(
            InsightCard(
                title=f"{label} is trending {direction}",
                summary=(
                    f"Projected terminal movement is {prediction.projected_change_pct * 100:.1f}% over the next {prediction.horizon} "
                    f"{prediction.time_grain} periods, based on {prediction.observed_points} observed periods."
                ),
                severity="warn" if direction == "down" else "info",
                recommended_action="Compare the strongest and weakest business slices, then validate whether the trend is broad-based.",
                evidence=[prediction.explanation or ""],
            )
        )
    if prediction.anomalies:
        top = sorted(prediction.anomalies, key=lambda item: abs(item.deviation), reverse=True)[0]
        cards.append(
            InsightCard(
                title=f"Strongest anomaly at {top.label}",
                summary=top.explanation or f"Observed value {top.value:.2f} deviated by {top.deviation:.2f} standard deviations.",
                severity="critical" if top.severity == "high" else "warn",
                recommended_action="Inspect channel, region, and product mixes around the anomaly period to isolate the driver.",
            )
        )
    if prediction.risk_band and prediction.risk_band != "unknown":
        cards.append(
            InsightCard(
                title=f"Target risk is {prediction.risk_band}",
                summary=(
                    f"Projected attainment risk is currently assessed as {prediction.risk_band}"
                    f"{f' for {label}' if label else ''}."
                ),
                severity="critical" if prediction.risk_band == "high" else "warn" if prediction.risk_band == "medium" else "info",
                recommended_action="Review the forecast together with targets and escalate corrective action if the trend persists.",
            )
        )
    if prediction.confidence_score is not None and prediction.confidence_score < 0.45:
        cards.append(
            InsightCard(
                title="Predictive confidence is limited",
                summary=(
                    f"Confidence is {prediction.confidence_score * 100:.0f}% because the available history is either short or volatile."
                ),
                severity="warn",
                recommended_action="Validate the recent time window and compare the result against a drilldown before acting on the forecast alone.",
            )
        )
    return cards


def build_segment_insights(segmentation: SegmentSummary, *, metric_focus: str | None = None) -> list[InsightCard]:
    if not segmentation.profiles:
        return []
    cards: list[InsightCard] = []
    largest = max(segmentation.profiles, key=lambda item: item.entity_count)
    cards.append(
        InsightCard(
            title=f"Largest segment: Cluster {largest.cluster_id}",
            summary=f"{largest.entity_count} entities fall into '{largest.label}'.",
            severity="info",
            recommended_action="Use this segment as the baseline when comparing outlier clusters.",
            evidence=largest.metric_highlights,
        )
    )
    if metric_focus:
        focus_profiles = sorted(
            segmentation.profiles,
            key=lambda item: item.centroid.get(metric_focus, 0.0),
            reverse=True,
        )
        top = focus_profiles[0]
        bottom = focus_profiles[-1]
        cards.append(
            InsightCard(
                title=f"{metric_focus} separates clusters clearly",
                summary=(
                    f"Cluster {top.cluster_id} leads on {metric_focus} while cluster {bottom.cluster_id} lags, "
                    "so these segments should be investigated separately before applying one action plan."
                ),
                severity="warn",
                recommended_action=(
                    f"Compare Cluster {top.cluster_id} with Cluster {bottom.cluster_id} to confirm which dimensions are driving the {metric_focus} gap."
                ),
            )
        )
    if segmentation.comparison_highlights:
        cards.append(
            InsightCard(
                title="Cluster comparison signal",
                summary=segmentation.comparison_highlights[0],
                severity="info",
                recommended_action="Compare the cluster profiles before moving to a single action plan.",
            )
        )
    return cards


def build_strategy_risk_insights(strategy: StrategyRiskSummary) -> list[InsightCard]:
    severity = "critical" if strategy.risk_band == "high" else "warn" if strategy.risk_band == "medium" else "info"
    return [
        InsightCard(
            title=f"KPI risk for {strategy.kpi_label or strategy.kpi_id}",
            summary=(
                (
                    f"{strategy.explanation} Confidence is {strategy.confidence_score * 100:.0f}%."
                    if strategy.explanation and strategy.confidence_score is not None
                    else strategy.explanation
                )
                or "Compare current KPI performance with the projected terminal value and configured target."
            ),
            severity=severity,  # type: ignore[arg-type]
            recommended_action=(
                strategy.recommended_actions[0]
                if strategy.recommended_actions
                else "Inspect the KPI in analytics, then forecast or segment the most relevant mart to explain the risk."
            ),
            evidence=strategy.supporting_details,
        )
    ]


def build_query_insights(rows: list[dict[str, Any]], query_spec: QuerySpec | None) -> list[InsightCard]:
    if not rows or not query_spec or not query_spec.measures:
        return []
    metric = query_spec.measures[0]
    dimension = query_spec.dimensions[0] if query_spec.dimensions else query_spec.time_field or "current view"
    first_row = rows[0]
    top_value = first_row.get(metric) or first_row.get("agg_value") or next(
        (value for key, value in first_row.items() if key != dimension),
        None,
    )
    return [
        InsightCard(
            title=f"Top signal by {dimension}",
            summary=f"The leading value in the current result set is {top_value} for the most prominent {dimension}.",
            severity="info",
            recommended_action="Drill into the leader and compare it against the next two groups before making a decision.",
        )
    ]


def build_suggested_actions(
    *,
    task_type: str,
    table: str | None,
    kpi_id: str | None = None,
    query_spec: QuerySpec | None = None,
    entity_field: str | None = None,
) -> list[SuggestedAction]:
    actions: list[SuggestedAction] = []
    if task_type in {"forecast", "anomaly", "strategy_risk"} and table:
        actions.append(
            SuggestedAction(
                action_type="segment",
                label="Segment the likely drivers",
                description="Find structural cohorts behind the trend, anomaly, or risk signal.",
                payload={"table": table, "entity_field": entity_field},
            )
        )
    if task_type == "segment" and table:
        actions.append(
            SuggestedAction(
                action_type="forecast",
                label="Forecast the leading metric",
                description="Project whether the strongest segment is improving or weakening.",
                payload={"table": table},
            )
        )
    if query_spec and query_spec.drill_dimensions:
        actions.append(
            SuggestedAction(
                action_type="drill",
                label="Take the next drill step",
                description=f"Continue down the preferred path: {query_spec.drill_dimensions[0]}",
                payload={"dimension": query_spec.drill_dimensions[0]},
            )
        )
    if kpi_id:
        actions.append(
            SuggestedAction(
                action_type="strategy_risk",
                label="Check KPI risk",
                description="Estimate target attainment risk for the matched KPI.",
                payload={"kpi_id": kpi_id},
            )
        )
    return actions
