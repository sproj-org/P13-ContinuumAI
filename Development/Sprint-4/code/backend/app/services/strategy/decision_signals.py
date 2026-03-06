"""Decision-surface signal generation from strategy evaluation output."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.kpi_registry import KPIRegistry
from app.models.strategy_bundle import StrategyBundle
from app.services.strategy.coverage import compute_readiness_and_coverage
from app.services.strategy.evaluation import evaluate_strategy
from app.services.strategy.schema_provider import load_dataset_schema
from app.services.strategy.storage import load_current_artifacts


def _severity_rank(value: str) -> int:
    lookup = {"critical": 0, "warn": 1, "info": 2}
    return lookup.get(value, 3)


def _map_rule_severity(value: str) -> str:
    if value == "block":
        return "critical"
    if value == "warn":
        return "warn"
    return "info"


def _status_signal_severity(status: str) -> str:
    if status == "red":
        return "critical"
    if status in {"yellow", "no_target", "unavailable"}:
        return "warn"
    return "info"


def _status_recommendation(status: str) -> str:
    if status == "red":
        return "Escalate immediately and assign an owner with a 7-day action plan."
    if status == "yellow":
        return "Monitor weekly and launch corrective actions to return to target."
    if status == "no_target":
        return "Define target thresholds so this KPI can drive actionable decisions."
    if status == "unavailable":
        return "Resolve schema dependencies and refresh KPI definition."
    return "Maintain current operating cadence."


def _render_narrative(summary: dict[str, int], readiness_score: float, notes: list[str]) -> str:
    critical = int(summary.get("critical", summary.get("kpis_critical", 0)))
    warning = int(summary.get("warning", summary.get("kpis_warning", 0)))
    on_track = int(summary.get("on_track", summary.get("kpis_on_track", 0)))
    rule_count = int(summary.get("triggered_rules", 0))

    base = (
        f"Readiness is at {readiness_score * 100:.1f}%. "
        f"{on_track} KPI(s) are on track, {warning} in warning, and {critical} in critical status. "
        f"{rule_count} rule(s) are currently triggered."
    )
    if notes:
        return base + " " + " ".join(notes[:2])
    return base


def build_decision_surface(
    *,
    dataset_id: str,
    db: Session,
    filters: list[dict[str, Any]] | None = None,
    time_range: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evaluation_payload = evaluate_strategy(
        dataset_id=dataset_id,
        db=db,
        filters=filters,
        time_range=time_range,
    )

    strategy_payload, kpi_payload, revision = load_current_artifacts()
    strategy_bundle = StrategyBundle.model_validate(strategy_payload)
    kpi_registry = KPIRegistry.model_validate(kpi_payload)
    schema_snapshot = load_dataset_schema(dataset_id)
    readiness, coverage_gaps, summaries, readiness_flags = compute_readiness_and_coverage(
        strategy_bundle=strategy_bundle,
        kpi_registry=kpi_registry,
        schema_snapshot=schema_snapshot,
    )

    on_track = 0
    warning = 0
    critical = 0
    signals: list[dict[str, Any]] = []
    recommendations: list[str] = []

    for kpi_row in evaluation_payload.get("kpis", []):
        kpi_id = str(kpi_row.get("id") or "")
        status = str(kpi_row.get("status") or "unknown")
        if status == "green":
            on_track += 1
        elif status in {"yellow", "no_target"}:
            warning += 1
        elif status in {"red", "unavailable"}:
            critical += 1
        else:
            warning += 1

        severity = _status_signal_severity(status)
        if severity in {"critical", "warn"}:
            explanation = (
                f"KPI '{kpi_id}' is in status '{status}' with value {kpi_row.get('value')} "
                f"against target {kpi_row.get('target')}."
            )
            action = _status_recommendation(status)
            signals.append(
                {
                    "id": f"signal_{kpi_id}",
                    "title": f"{kpi_row.get('display_name') or kpi_id} requires attention",
                    "severity": severity,
                    "explanation": explanation,
                    "suggested_action": action,
                    "kpi_id": kpi_id,
                    "source": "kpi_status",
                }
            )
            recommendations.append(action)

    for rule_row in evaluation_payload.get("triggered_rules", []):
        severity = _map_rule_severity(str(rule_row.get("severity") or "info"))
        action = str(rule_row.get("action") or "Review triggered rule and assign an owner.")
        signals.append(
            {
                "id": f"rule_{rule_row.get('id')}",
                "title": f"Rule triggered: {rule_row.get('id')}",
                "severity": severity,
                "explanation": f"Condition '{rule_row.get('condition')}' evaluated to true.",
                "suggested_action": action,
                "kpi_ids": rule_row.get("affected_kpis", []),
                "source": "rule_trigger",
            }
        )
        recommendations.append(action)

    for gap in coverage_gaps[:5]:
        signals.append(
            {
                "id": f"gap_{gap.kpi_id}",
                "title": f"Dependency gap: {gap.kpi_id}",
                "severity": "warn",
                "explanation": "KPI has unresolved mart or column dependencies.",
                "suggested_action": "Review mart mappings and required columns in KPI Library or Advanced YAML.",
                "kpi_id": gap.kpi_id,
                "source": "coverage_gap",
            }
        )

    signals.sort(key=lambda item: (_severity_rank(str(item.get("severity"))), str(item.get("title") or "")))
    unique_recommendations: list[str] = []
    seen_recommendations: set[str] = set()
    for item in recommendations:
        if item in seen_recommendations:
            continue
        seen_recommendations.add(item)
        unique_recommendations.append(item)

    summary = {
        "overall_readiness_score": readiness.overall_score,
        "kpis_on_track": on_track,
        "kpis_warning": warning,
        "kpis_critical": critical,
        "triggered_rules": len(evaluation_payload.get("triggered_rules", [])),
    }
    readiness_notes = []
    raw_notes = summaries.get("readiness_notes") if isinstance(summaries, dict) else None
    if isinstance(raw_notes, list):
        readiness_notes.extend(str(item) for item in raw_notes if str(item).strip())
    if readiness_flags.placeholders:
        readiness_notes.extend(
            item for item in readiness_flags.placeholders if item not in readiness_notes
        )
    narrative = _render_narrative(summary, readiness.overall_score, readiness_notes)

    return {
        "dataset_id": dataset_id,
        "revision": revision,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "executive_summary": {
            **summary,
            "narrative": narrative,
        },
        "decision_signals": signals,
        "recommendations": unique_recommendations[:8],
    }
