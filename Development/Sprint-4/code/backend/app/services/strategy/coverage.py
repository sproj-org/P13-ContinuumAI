"""Readiness scoring and KPI coverage analysis for Task-2."""

from __future__ import annotations

import re
from typing import Any

from app.models.decision_state import CoverageGapItem, DecisionReadiness, ReadinessFlags
from app.models.kpi_registry import KPIRegistry
from app.models.strategy_bundle import StrategyBundle
from app.services.strategy.schema_provider import DatasetSchemaSnapshot

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CONDITION_KEYWORDS = {
    "and",
    "or",
    "not",
    "if",
    "then",
    "else",
    "true",
    "false",
    "null",
}


def _clamp_01(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return value


def _condition_identifiers(condition: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(condition)
        if token.lower() not in _CONDITION_KEYWORDS
    }


def _compute_rule_readiness(
    *,
    kpi_ids: set[str],
    strategy_bundle: StrategyBundle,
) -> tuple[float, int, int]:
    rules = strategy_bundle.decision_rules
    if not rules:
        return 1.0, 0, 0

    ready = 0
    unknown_ref_count = 0
    for rule in rules:
        identifiers = _condition_identifiers(rule.condition or "")
        unknown = [item for item in identifiers if item not in kpi_ids]
        if not unknown:
            ready += 1
        else:
            unknown_ref_count += len(unknown)

    return _clamp_01(ready / len(rules)), ready, unknown_ref_count


def _weights(strategy_bundle: StrategyBundle) -> dict[str, float]:
    values = strategy_bundle.scoring_model.weights
    return {
        "kpi_coverage": float(values.kpi_coverage),
        "rule_readiness": float(values.rule_readiness),
        "hierarchy_readiness": float(values.hierarchy_readiness),
        "data_readiness": float(values.data_readiness),
    }


def compute_readiness_and_coverage(
    *,
    strategy_bundle: StrategyBundle,
    kpi_registry: KPIRegistry,
    schema_snapshot: DatasetSchemaSnapshot,
) -> tuple[DecisionReadiness, list[CoverageGapItem], dict[str, Any], ReadinessFlags]:
    total_kpis = len(kpi_registry.kpis)
    kpis_with_full_dependencies = 0
    coverage_gaps: list[CoverageGapItem] = []

    required_columns_total = 0
    missing_columns_total = 0

    for kpi in kpi_registry.kpis:
        missing_marts = [mart for mart in kpi.marts if mart not in schema_snapshot.available_marts]
        missing_columns_by_mart: dict[str, list[str]] = {}

        for mart_id in kpi.marts:
            if mart_id not in schema_snapshot.available_marts:
                continue
            required_columns_total += len(kpi.required_columns)
            available_columns = schema_snapshot.mart_columns.get(mart_id, set())
            missing_columns = [column for column in kpi.required_columns if column not in available_columns]
            if missing_columns:
                missing_columns_total += len(missing_columns)
                missing_columns_by_mart[mart_id] = missing_columns

        if not missing_marts and not missing_columns_by_mart:
            kpis_with_full_dependencies += 1
            continue

        coverage_gaps.append(
            CoverageGapItem(
                kpi_id=kpi.id,
                reason="missing_dependencies",
                details={
                    "missing_marts": missing_marts,
                    "missing_columns_by_mart": missing_columns_by_mart,
                },
            )
        )

    kpis_defined = total_kpis > 0
    kpi_coverage = _clamp_01(kpis_with_full_dependencies / total_kpis) if kpis_defined else 0.0
    if not kpis_defined:
        data_readiness = 0.0
    elif required_columns_total > 0:
        data_readiness = _clamp_01(1.0 - (missing_columns_total / required_columns_total))
    else:
        data_readiness = 1.0

    kpi_ids = {kpi.id for kpi in kpi_registry.kpis}
    rule_readiness, ready_rules, unknown_rule_references = _compute_rule_readiness(
        kpi_ids=kpi_ids,
        strategy_bundle=strategy_bundle,
    )
    hierarchy_readiness = 1.0
    placeholders = ["hierarchy_readiness_placeholder"]

    weights = _weights(strategy_bundle)
    total_weight = sum(weights.values()) or 1.0
    if not kpis_defined:
        overall_score = 0.0
        placeholders.append("no_kpis_defined")
        explanation = (
            "No KPIs defined yet; readiness is preliminary. "
            "Add KPIs to enable coverage and data readiness calculations. "
            "Hierarchy readiness is placeholder in Sprint-4; will be implemented in Strategy Expansion Track."
        )
    else:
        overall_score = _clamp_01(
            (
                (kpi_coverage * weights["kpi_coverage"])
                + (rule_readiness * weights["rule_readiness"])
                + (hierarchy_readiness * weights["hierarchy_readiness"])
                + (data_readiness * weights["data_readiness"])
            )
            / total_weight
        )
        explanation = (
            f"KPIs with full dependencies: {kpis_with_full_dependencies}/{total_kpis}. "
            f"Missing columns: {missing_columns_total}/{required_columns_total or 0}. "
            f"Rule conditions validated: {ready_rules}/{len(strategy_bundle.decision_rules)}. "
            "Hierarchy readiness is placeholder in Sprint-4; will be implemented in Strategy Expansion Track."
        )

    readiness = DecisionReadiness(
        overall_score=overall_score,
        kpi_coverage=kpi_coverage,
        rule_readiness=rule_readiness,
        hierarchy_readiness=hierarchy_readiness,
        data_readiness=data_readiness,
        explanation=explanation,
    )
    readiness_flags = ReadinessFlags(kpis_defined=kpis_defined, placeholders=placeholders)

    summaries = {
        "dataset_id": schema_snapshot.dataset_id,
        "total_kpis": total_kpis,
        "kpis_with_full_dependencies": kpis_with_full_dependencies,
        "missing_columns_total": missing_columns_total,
        "required_columns_total": required_columns_total,
        "rules_total": len(strategy_bundle.decision_rules),
        "rules_ready": ready_rules,
        "unknown_rule_references": unknown_rule_references,
        "available_marts": sorted(schema_snapshot.available_marts),
        "unavailable_marts": schema_snapshot.unavailable_marts,
        "notes": schema_snapshot.notes,
        "hierarchy_readiness_note": "not implemented in Task 2",
    }
    return readiness, coverage_gaps, summaries, readiness_flags
