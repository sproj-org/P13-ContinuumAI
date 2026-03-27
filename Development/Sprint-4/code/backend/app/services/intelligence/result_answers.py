"""Deterministic follow-up answers for structured analysis results."""

from __future__ import annotations

from statistics import mean
from typing import Any

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


def _segment_primary_metric(profiles: list[SegmentProfile]) -> str | None:
    centroid_keys = {key for profile in profiles for key in profile.centroid}
    if not centroid_keys:
        return None
    best_metric: str | None = None
    best_span = -1.0
    for metric in centroid_keys:
        values = [profile.centroid.get(metric, 0.0) for profile in profiles]
        span = max(values) - min(values)
        if span > best_span:
            best_metric = metric
            best_span = span
    return best_metric


def _profile_digest(profile: SegmentProfile, primary_metric: str | None = None) -> dict[str, Any]:
    digest: dict[str, Any] = {
        "cluster_id": profile.cluster_id,
        "label": profile.label,
        "entity_count": profile.entity_count,
        "metric_highlights": profile.metric_highlights[:4],
    }
    if primary_metric:
        digest["primary_metric"] = primary_metric
        digest["primary_metric_value"] = profile.centroid.get(primary_metric)
    return digest


def _segment_evidence(analysis: AnalysisResponse) -> dict[str, Any] | None:
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
    primary_metric = _segment_primary_metric(profiles)
    strongest = max(profiles, key=lambda item: item.centroid.get(primary_metric or "", 0.0))
    weakest = min(profiles, key=lambda item: item.centroid.get(primary_metric or "", 0.0))
    return {
        "cluster_count": segmentation.cluster_count,
        "primary_metric": primary_metric,
        "largest_cluster": _profile_digest(largest, primary_metric),
        "smallest_cluster": _profile_digest(smallest, primary_metric),
        "most_distinctive_cluster": _profile_digest(most_distinctive, primary_metric),
        "strongest_cluster": _profile_digest(strongest, primary_metric),
        "weakest_cluster": _profile_digest(weakest, primary_metric),
        "comparison_highlights": segmentation.comparison_highlights[:4],
    }


def _forecast_evidence(analysis: AnalysisResponse) -> dict[str, Any] | None:
    prediction = analysis.prediction
    if prediction is None or prediction.mode != "forecast":
        return None

    observed_points = [point for point in prediction.points if point.actual is not None]
    evidence: dict[str, Any] = {
        "metric": prediction.metric,
        "display_label": prediction.display_label,
        "observed_points": prediction.observed_points,
        "horizon": prediction.horizon,
        "confidence_score": prediction.confidence_score,
        "risk_band": prediction.risk_band,
        "target_value": prediction.target_value,
        "explanation": prediction.explanation,
    }
    if observed_points:
        start = observed_points[0]
        end = observed_points[-1]
        delta = (end.actual or 0.0) - (start.actual or 0.0)
        pct_change = None
        if start.actual not in (None, 0.0, -0.0):
            pct_change = delta / abs(start.actual)
        evidence["observed_window"] = {
            "start_label": start.label,
            "start_value": start.actual,
            "end_label": end.label,
            "end_value": end.actual,
            "delta": delta,
            "pct_change": pct_change,
        }
    forecast_points = [point for point in prediction.points if point.is_forecast and point.forecast is not None]
    if forecast_points:
        final_point = forecast_points[-1]
        evidence["projected_terminal"] = {
            "label": final_point.label,
            "forecast": final_point.forecast,
            "lower": final_point.lower,
            "upper": final_point.upper,
        }
        if prediction.target_value is not None and final_point.forecast is not None:
            evidence["target_gap"] = final_point.forecast - prediction.target_value
    if prediction.anomalies:
        top_anomaly = sorted(prediction.anomalies, key=lambda item: abs(item.deviation), reverse=True)[0]
        evidence["top_anomaly"] = {
            "label": top_anomaly.label,
            "severity": top_anomaly.severity,
            "value": top_anomaly.value,
            "deviation": top_anomaly.deviation,
            "explanation": top_anomaly.explanation,
        }
    return evidence


def _anomaly_evidence(analysis: AnalysisResponse) -> dict[str, Any] | None:
    prediction = analysis.prediction
    if prediction is None or not prediction.anomalies:
        return None
    strongest = sorted(prediction.anomalies, key=lambda item: abs(item.deviation), reverse=True)[0]
    return {
        "anomaly_count": len(prediction.anomalies),
        "strongest_anomaly": {
            "label": strongest.label,
            "severity": strongest.severity,
            "value": strongest.value,
            "deviation": strongest.deviation,
            "explanation": strongest.explanation,
        },
        "display_label": prediction.display_label,
        "metric": prediction.metric,
    }


def _risk_evidence(analysis: AnalysisResponse) -> dict[str, Any] | None:
    strategy = analysis.strategy
    if strategy is None:
        return None
    evidence: dict[str, Any] = {
        "kpi_id": strategy.kpi_id,
        "kpi_label": strategy.kpi_label,
        "current_value": strategy.current_value,
        "projected_value": strategy.projected_value,
        "target_value": strategy.target_value,
        "variance_to_target": strategy.variance_to_target,
        "risk_band": strategy.risk_band,
        "confidence_score": strategy.confidence_score,
        "target_horizon": strategy.target_horizon,
        "forecast_basis": strategy.forecast_basis,
        "explanation": strategy.explanation,
        "supporting_details": strategy.supporting_details[:4],
        "recommended_actions": strategy.recommended_actions[:3],
    }
    if analysis.prediction is not None and analysis.prediction.anomalies:
        strongest = sorted(analysis.prediction.anomalies, key=lambda item: abs(item.deviation), reverse=True)[0]
        evidence["top_anomaly"] = {
            "label": strongest.label,
            "severity": strongest.severity,
            "deviation": strongest.deviation,
            "explanation": strongest.explanation,
        }
    return evidence


def build_analysis_answer_evidence(analysis: AnalysisResponse) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    segment = _segment_evidence(analysis)
    if segment:
        evidence["segmentation"] = segment
    forecast = _forecast_evidence(analysis)
    if forecast:
        evidence["forecast"] = forecast
    anomaly = _anomaly_evidence(analysis)
    if anomaly:
        evidence["anomaly"] = anomaly
    risk = _risk_evidence(analysis)
    if risk:
        evidence["risk"] = risk
    return evidence


def _answer_segment_question(
    message: str,
    analysis: AnalysisResponse,
    artifact_action: str | None,
    answer_mode: str | None,
) -> str | None:
    evidence = _segment_evidence(analysis)
    if evidence is None:
        return None

    largest = evidence["largest_cluster"]
    most_distinctive = evidence["most_distinctive_cluster"]
    strongest = evidence["strongest_cluster"]
    weakest = evidence["weakest_cluster"]
    primary_metric = evidence.get("primary_metric")
    text = _normalize_text(message)

    if (
        answer_mode == "segment_comparison"
        or artifact_action == "segment_compare_extremes"
        or _contains_any(text, ("strongest", "weakest", "strongest cluster", "weakest cluster"))
    ):
        strongest_metric = strongest["metric_highlights"][0] if strongest.get("metric_highlights") else "its leading metrics"
        weakest_metric = weakest["metric_highlights"][0] if weakest.get("metric_highlights") else "its weakest metrics"
        metric_text = f" on {primary_metric}" if primary_metric else ""
        return (
            f"Cluster {strongest['cluster_id']} is strongest{metric_text}, while Cluster {weakest['cluster_id']} trails most clearly{metric_text}. "
            f"Use Cluster {largest['cluster_id']} as the operating baseline if you also need a broad-volume reference. Compare {strongest_metric} against {weakest_metric} first."
        )

    if (
        answer_mode == "segment_differentiation"
        or artifact_action == "segment_differentiators"
        or _contains_any(text, ("differentiate", "differentiates", "difference", "different"))
    ):
        differentiators = list(most_distinctive.get("metric_highlights") or [])[:3]
        highlight_text = ", ".join(differentiators) if differentiators else "its centroid metrics"
        return (
            f"Cluster {most_distinctive['cluster_id']} stands out the most from the pack. The clearest differentiators are {highlight_text}. "
            f"{evidence['comparison_highlights'][0] if evidence.get('comparison_highlights') else 'Use those feature gaps to compare clusters side by side.'}"
        )

    if (
        answer_mode in {"drill_priority", "next_best_action"}
        or artifact_action == "segment_drill_priority"
        or _contains_any(text, ("drill", "inspect first", "start with"))
    ):
        priority = most_distinctive
        return (
            f"Start with Cluster {priority['cluster_id']}. It is the most behaviorally distinct segment, which makes it the fastest place to find a concrete driver. "
            f"{priority['metric_highlights'][0] if priority.get('metric_highlights') else priority.get('label')}"
        )

    return (
        f"The segmentation produced {evidence['cluster_count']} clusters. Cluster {largest['cluster_id']} is the largest, "
        f"and Cluster {most_distinctive['cluster_id']} is the most distinctive."
    )


def _answer_forecast_question(
    message: str,
    analysis: AnalysisResponse,
    artifact_action: str | None,
    answer_mode: str | None,
) -> str | None:
    prediction = analysis.prediction
    evidence = _forecast_evidence(analysis)
    if prediction is None or evidence is None:
        return None
    text = _normalize_text(message)
    observed_window = evidence.get("observed_window") or {}

    if answer_mode == "what_happened" and observed_window:
        delta = observed_window.get("delta") or 0.0
        pct = observed_window.get("pct_change")
        direction = "rose" if delta >= 0 else "fell"
        pct_text = f" ({pct * 100:.1f}%)" if pct is not None else ""
        return (
            f"The clearest movement in the observed window is that {prediction.display_label or prediction.metric} "
            f"{direction} from {_format_number(observed_window.get('start_value'))} at {observed_window.get('start_label')} "
            f"to {_format_number(observed_window.get('end_value'))} at {observed_window.get('end_label')}{pct_text}. "
            f"{prediction.explanation or 'The forecast then extends that recent pattern forward.'}"
        )

    if (
        answer_mode == "forecast_interpretation"
        or artifact_action == "forecast_drivers"
        or _contains_any(text, ("driving", "driver", "why", "projected change"))
    ):
        anomaly_text = ""
        anomaly = evidence.get("top_anomaly") if isinstance(evidence.get("top_anomaly"), dict) else None
        if anomaly:
            anomaly_text = (
                f" The sharpest recent disruption was {anomaly.get('label')}, where "
                f"{anomaly.get('explanation') or 'the metric deviated materially from expectation'}."
            )
        return (
            f"The forecast is primarily driven by the recent observed trend across {prediction.observed_points} periods"
            f"{f' for {prediction.display_label or prediction.metric}' if prediction.display_label or prediction.metric else ''}. "
            f"{prediction.explanation or 'The model extends the latest level-and-trend pattern rather than inventing a new regime.'}"
            f"{anomaly_text}"
        )

    if artifact_action == "forecast_target_gap" or _contains_any(text, ("target", "gap", "miss", "hit target")):
        projected_terminal = evidence.get("projected_terminal") if isinstance(evidence.get("projected_terminal"), dict) else {}
        return (
            f"The projection moves toward {_format_number(projected_terminal.get('forecast'))} "
            f"against a target of {_format_number(prediction.target_value)}. "
            f"Risk is currently assessed as {prediction.risk_band or 'unknown'}."
        )

    if _contains_any(text, ("confidence", "uncertainty", "certain")):
        return (
            f"Confidence is {_format_number((prediction.confidence_score or 0.0) * 100)}%. "
            "This is a lightweight trend model, so treat it as directional guidance rather than a calibrated confidence interval."
        )

    return prediction.explanation or "The forecast extends the recent trend using the available historical window."


def _answer_anomaly_question(
    message: str,
    analysis: AnalysisResponse,
    artifact_action: str | None,
    answer_mode: str | None,
) -> str | None:
    prediction = analysis.prediction
    evidence = _anomaly_evidence(analysis)
    if prediction is None or evidence is None:
        return None
    text = _normalize_text(message)
    strongest = evidence["strongest_anomaly"]
    strongest_explanation = strongest.get("explanation") or (
        f"Observed value {_format_number(strongest.get('value'))} deviated by {strongest.get('deviation', 0.0):.2f} standard deviations."
    )

    if answer_mode == "what_happened":
        return (
            f"The most meaningful break happened at {strongest['label']}. "
            f"{strongest_explanation}"
        )

    if artifact_action == "anomaly_driver" or _contains_any(text, ("driving", "driver", "most anomalous", "why")):
        return (
            f"The strongest anomaly is at {strongest['label']}. "
            f"{strongest_explanation}"
        )

    if artifact_action == "anomaly_scope" or _contains_any(text, ("broad", "isolated", "scope", "where", "when")):
        scope = "broad-based" if evidence["anomaly_count"] >= 3 else "more isolated"
        return (
            f"This looks {scope}. {evidence['anomaly_count']} periods were flagged, with the most severe break at {strongest['label']}. "
            "Compare the anomaly period against the immediately preceding periods and the main business slices next."
        )

    return strongest.get("explanation") or "The strongest anomaly materially deviated from the recent baseline."


def _answer_risk_question(
    message: str,
    analysis: AnalysisResponse,
    artifact_action: str | None,
    answer_mode: str | None,
) -> str | None:
    strategy = analysis.strategy
    prediction = analysis.prediction
    evidence = _risk_evidence(analysis)
    if strategy is None or evidence is None:
        return None
    text = _normalize_text(message)

    if answer_mode == "strategy_alignment":
        return (
            f"{strategy.kpi_label or strategy.kpi_id} matters strategically because it is tracking {_format_number(evidence.get('current_value'))} "
            f"toward {_format_number(evidence.get('projected_value'))} against a target of {_format_number(evidence.get('target_value'))}. "
            f"That keeps the KPI in a {evidence.get('risk_band')} risk band and should shape the next investigation and corrective action."
        )

    if artifact_action == "risk_driver" or _contains_any(text, ("why", "driving", "driver", "at risk")):
        return (
            f"{strategy.kpi_label or strategy.kpi_id} is currently assessed as {strategy.risk_band} risk because "
            f"current performance {_format_number(evidence.get('current_value'))} is tracking toward {_format_number(evidence.get('projected_value'))} "
            f"against a target of {_format_number(evidence.get('target_value'))}. "
            f"{strategy.explanation or ''}".strip()
        )

    if artifact_action == "risk_slice" or _contains_any(text, ("slice", "segment", "business slice")):
        if evidence.get("supporting_details"):
            return (
                f"Start with the most relevant operating slice referenced in the current risk context. "
                f"{evidence['supporting_details'][0]}"
            )
        return "Start with the first drill dimension on the linked KPI and compare the weakest business slice against the strongest."

    if answer_mode == "next_best_action" or artifact_action == "risk_next_step" or _contains_any(text, ("next", "what should", "investigate")):
        recommended = evidence["recommended_actions"][0] if evidence.get("recommended_actions") else None
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
    answer_mode: str | None = None,
) -> str | None:
    if analysis.segmentation is not None:
        answer = _answer_segment_question(message, analysis, artifact_action, answer_mode)
        if answer:
            return answer
    if analysis.strategy is not None:
        answer = _answer_risk_question(message, analysis, artifact_action, answer_mode)
        if answer:
            return answer
    if analysis.prediction is not None and analysis.prediction.mode == "forecast":
        answer = _answer_forecast_question(message, analysis, artifact_action, answer_mode)
        if answer:
            return answer
    if analysis.prediction is not None and analysis.prediction.mode == "anomaly":
        answer = _answer_anomaly_question(message, analysis, artifact_action, answer_mode)
        if answer:
            return answer
    return None
