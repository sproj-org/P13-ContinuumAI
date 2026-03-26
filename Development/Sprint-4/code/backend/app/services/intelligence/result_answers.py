"""Deterministic follow-up answers for structured analysis results."""

from __future__ import annotations

from statistics import mean

from app.services.intelligence.specs import AnalysisResponse, SegmentProfile


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").lower().replace("_", " ").split())


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _format_number(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:,.2f}"


def _segment_divergence(profile: SegmentProfile, comparison_means: dict[str, float]) -> float:
    score = 0.0
    for metric, value in profile.centroid.items():
        score += abs(value - comparison_means.get(metric, 0.0))
    return score


def _answer_segment_question(message: str, analysis: AnalysisResponse, artifact_action: str | None) -> str | None:
    segmentation = analysis.segmentation
    if segmentation is None or not segmentation.profiles:
        return None

    profiles = list(segmentation.profiles)
    largest = max(profiles, key=lambda item: item.entity_count)
    smallest = min(profiles, key=lambda item: item.entity_count)
    centroid_means: dict[str, float] = {}
    centroid_keys = {key for profile in profiles for key in profile.centroid}
    for key in centroid_keys:
        centroid_means[key] = mean(profile.centroid.get(key, 0.0) for profile in profiles)
    most_distinctive = max(profiles, key=lambda item: _segment_divergence(item, centroid_means))
    text = _normalize_text(message)

    if artifact_action == "segment_compare_extremes" or _contains_any(text, ("strongest", "weakest", "strongest cluster", "weakest cluster")):
        strongest_metric = profiles[0].metric_highlights[0] if profiles[0].metric_highlights else "its leading metrics"
        weakest_metric = profiles[-1].metric_highlights[0] if profiles[-1].metric_highlights else "its weakest metrics"
        return (
            f"Cluster {largest.cluster_id} is the broadest segment with {largest.entity_count} entities and is useful as the operating baseline, "
            f"while Cluster {smallest.cluster_id} is the smallest and most niche. Compare {strongest_metric} against {weakest_metric} first."
        )

    if artifact_action == "segment_differentiators" or _contains_any(text, ("differentiate", "differentiates", "difference", "different")):
        differentiators = most_distinctive.metric_highlights[:3]
        highlight_text = ", ".join(differentiators) if differentiators else "its centroid metrics"
        return (
            f"Cluster {most_distinctive.cluster_id} stands out the most from the pack. The clearest differentiators are {highlight_text}. "
            f"{segmentation.comparison_highlights[0] if segmentation.comparison_highlights else 'Use those feature gaps to compare clusters side by side.'}"
        )

    if artifact_action == "segment_drill_priority" or _contains_any(text, ("drill", "inspect first", "start with")):
        priority = most_distinctive
        return (
            f"Start with Cluster {priority.cluster_id}. It is the most behaviorally distinct segment, which makes it the fastest place to find a concrete driver. "
            f"{priority.metric_highlights[0] if priority.metric_highlights else priority.label}"
        )

    return (
        f"The segmentation produced {segmentation.cluster_count} clusters. Cluster {largest.cluster_id} is the largest, "
        f"and Cluster {most_distinctive.cluster_id} is the most distinctive."
    )


def _answer_forecast_question(message: str, analysis: AnalysisResponse, artifact_action: str | None) -> str | None:
    prediction = analysis.prediction
    if prediction is None:
        return None
    text = _normalize_text(message)

    if artifact_action == "forecast_drivers" or _contains_any(text, ("driving", "driver", "why", "projected change")):
        anomaly_text = ""
        if prediction.anomalies:
            anomaly = sorted(prediction.anomalies, key=lambda item: abs(item.deviation), reverse=True)[0]
            anomaly_text = f" The sharpest recent disruption was {anomaly.label}, where {anomaly.explanation or 'the metric deviated materially from expectation'}."
        return (
            f"The forecast is primarily driven by the recent observed trend across {prediction.observed_points} periods"
            f"{f' for {prediction.display_label or prediction.metric}' if prediction.display_label or prediction.metric else ''}. "
            f"{prediction.explanation or 'The model extends the latest level-and-trend pattern rather than inventing a new regime.'}"
            f"{anomaly_text}"
        )

    if artifact_action == "forecast_target_gap" or _contains_any(text, ("target", "gap", "miss", "hit target")):
        return (
            f"The projection moves toward {_format_number(prediction.points[-1].forecast if prediction.points else None)} "
            f"against a target of {_format_number(prediction.target_value)}. "
            f"Risk is currently assessed as {prediction.risk_band or 'unknown'}."
        )

    if _contains_any(text, ("confidence", "uncertainty", "certain")):
        return (
            f"Confidence is {_format_number((prediction.confidence_score or 0.0) * 100)}%. "
            "This is a lightweight trend model, so treat it as directional guidance rather than a calibrated confidence interval."
        )

    return prediction.explanation or "The forecast extends the recent trend using the available historical window."


def _answer_anomaly_question(message: str, analysis: AnalysisResponse, artifact_action: str | None) -> str | None:
    prediction = analysis.prediction
    if prediction is None or not prediction.anomalies:
        return None
    text = _normalize_text(message)
    strongest = sorted(prediction.anomalies, key=lambda item: abs(item.deviation), reverse=True)[0]

    if artifact_action == "anomaly_driver" or _contains_any(text, ("driving", "driver", "most anomalous", "why")):
        return (
            f"The strongest anomaly is at {strongest.label}. "
            f"{strongest.explanation or f'Observed value {_format_number(strongest.value)} deviated by {strongest.deviation:.2f} standard deviations.'}"
        )

    if artifact_action == "anomaly_scope" or _contains_any(text, ("broad", "isolated", "scope", "where", "when")):
        scope = "broad-based" if len(prediction.anomalies) >= 3 else "more isolated"
        return (
            f"This looks {scope}. {len(prediction.anomalies)} periods were flagged, with the most severe break at {strongest.label}. "
            "Compare the anomaly period against the immediately preceding periods and the main business slices next."
        )

    return strongest.explanation or "The strongest anomaly materially deviated from the recent baseline."


def _answer_risk_question(message: str, analysis: AnalysisResponse, artifact_action: str | None) -> str | None:
    strategy = analysis.strategy
    prediction = analysis.prediction
    if strategy is None:
        return None
    text = _normalize_text(message)

    if artifact_action == "risk_driver" or _contains_any(text, ("why", "driving", "driver", "at risk")):
        return (
            f"{strategy.kpi_label or strategy.kpi_id} is currently assessed as {strategy.risk_band} risk because "
            f"current performance {_format_number(strategy.current_value)} is tracking toward {_format_number(strategy.projected_value)} "
            f"against a target of {_format_number(strategy.target_value)}. "
            f"{strategy.explanation or ''}".strip()
        )

    if artifact_action == "risk_slice" or _contains_any(text, ("slice", "segment", "business slice")):
        if strategy.supporting_details:
            return (
                f"Start with the most relevant operating slice referenced in the current risk context. "
                f"{strategy.supporting_details[0]}"
            )
        return "Start with the first drill dimension on the linked KPI and compare the weakest business slice against the strongest."

    if artifact_action == "risk_next_step" or _contains_any(text, ("next", "what should", "investigate")):
        recommended = strategy.recommended_actions[0] if strategy.recommended_actions else None
        if recommended:
            return recommended
        if prediction is not None and prediction.anomalies:
            return "Inspect the most severe anomaly period first, then segment the likely drivers if the issue is concentrated in a specific slice."
        return "Inspect the KPI in analytics, compare the weakest business slices, then segment the likely drivers if the gap persists."

    return strategy.explanation or "Compare the current KPI value, target, and projected path to assess the source of risk."


def answer_analysis_question(
    *,
    message: str,
    analysis: AnalysisResponse,
    artifact_action: str | None = None,
) -> str | None:
    if analysis.segmentation is not None:
        answer = _answer_segment_question(message, analysis, artifact_action)
        if answer:
            return answer
    if analysis.strategy is not None:
        answer = _answer_risk_question(message, analysis, artifact_action)
        if answer:
            return answer
    if analysis.prediction is not None and analysis.prediction.mode == "forecast":
        answer = _answer_forecast_question(message, analysis, artifact_action)
        if answer:
            return answer
    if analysis.prediction is not None and analysis.prediction.mode == "anomaly":
        answer = _answer_anomaly_question(message, analysis, artifact_action)
        if answer:
            return answer
    return None
