"""Strategy evaluation service for KPI/target execution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.kpi_registry import KPIRegistry
from app.models.strategy_bundle import StrategyBundle, TargetThreshold
from app.services.strategy.evaluator import evaluate_kpi_formula
from app.services.strategy.schema_provider import load_dataset_schema
from app.services.strategy.storage import load_current_artifacts

KpiStatus = Literal["green", "yellow", "red", "no_target", "unavailable"]


def _target_entry(kpi_id: str, strategy_bundle: StrategyBundle) -> TargetThreshold | None:
    return strategy_bundle.targets.get(kpi_id)


def _compute_target_status(
    *,
    value: float | None,
    target: TargetThreshold | None,
) -> tuple[KpiStatus, float | None]:
    if value is None:
        return "unavailable", None
    if target is None:
        return "no_target", None

    variance = float(value) - float(target.target)
    direction = target.direction
    yellow = target.yellow_threshold
    red = target.red_threshold

    if direction == "up":
        if value >= target.target:
            return "green", variance
        if yellow is not None and value >= yellow:
            return "yellow", variance
        if red is not None and value < red:
            return "red", variance
        return "yellow", variance

    # direction == "down"
    if value <= target.target:
        return "green", variance
    if yellow is not None and value <= yellow:
        return "yellow", variance
    if red is not None and value > red:
        return "red", variance
    return "yellow", variance


def evaluate_strategy(
    *,
    dataset_id: str,
    db: Session,
    filters: list[dict[str, Any]] | None = None,
    time_range: dict[str, Any] | None = None,
) -> dict[str, Any]:
    strategy_payload, kpi_payload, revision = load_current_artifacts()
    strategy_bundle = StrategyBundle.model_validate(strategy_payload)
    kpi_registry = KPIRegistry.model_validate(kpi_payload)
    schema_snapshot = load_dataset_schema(dataset_id)

    kpi_results: list[dict[str, Any]] = []
    for kpi in kpi_registry.kpis:
        computed = evaluate_kpi_formula(
            dataset_id=dataset_id,
            kpi=kpi,
            db=db,
            filters=filters,
            time_range=time_range,
            schema_snapshot=schema_snapshot,
        )
        value = computed.get("value")
        target = _target_entry(kpi.id, strategy_bundle)
        status, variance = _compute_target_status(value=value, target=target)

        kpi_results.append(
            {
                "id": kpi.id,
                "value": value,
                "target": target.target if target else None,
                "variance": variance,
                "status": status,
                "provenance": computed.get("provenance"),
            }
        )

    return {
        "dataset_id": dataset_id,
        "revision": revision,
        "kpis": kpi_results,
        "triggered_rules": [],
        "evaluation_time": datetime.now(timezone.utc).isoformat(),
    }
