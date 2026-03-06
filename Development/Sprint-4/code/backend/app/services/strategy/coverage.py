"""Readiness scoring and KPI coverage analysis for Strategy workspace."""

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
_RULE_REFERENCE_RE = re.compile(r"""(?:kpi|target)\(\s*["']([^"']+)["']\s*\)""")


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


def _rule_references(condition: str) -> set[str]:
    refs = {item.strip() for item in _RULE_REFERENCE_RE.findall(condition) if item.strip()}
    if refs:
        return refs
    return _condition_identifiers(condition)


def _compute_rule_completeness(
    *,
    kpi_ids: set[str],
    strategy_bundle: StrategyBundle,
) -> tuple[float, int, int]:
    rules = strategy_bundle.decision_rules
    if not rules:
        return 0.0, 0, 0

    valid_rules = 0
    unknown_ref_count = 0
    for rule in rules:
        identifiers = _rule_references(rule.condition or "")
        unknown = [item for item in identifiers if item not in kpi_ids]
        if not unknown:
            valid_rules += 1
        else:
            unknown_ref_count += len(unknown)

    return _clamp_01(valid_rules / len(rules)), valid_rules, unknown_ref_count


def _legacy_weights(strategy_bundle: StrategyBundle) -> dict[str, float]:
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
    kpi_completeness = _clamp_01(kpis_with_full_dependencies / total_kpis) if kpis_defined else 0.0
    if not kpis_defined:
        data_readiness = 0.0
    elif required_columns_total > 0:
        data_readiness = _clamp_01(1.0 - (missing_columns_total / required_columns_total))
    else:
        data_readiness = 1.0

    targets = strategy_bundle.targets or {}
    targets_defined = len(targets) > 0
    kpis_with_targets = len([kpi for kpi in kpi_registry.kpis if kpi.id in targets])
    target_completeness = _clamp_01(kpis_with_targets / total_kpis) if kpis_defined else 0.0

    kpi_ids = {kpi.id for kpi in kpi_registry.kpis}
    rule_completeness, valid_rules, unknown_rule_references = _compute_rule_completeness(
        kpi_ids=kpi_ids,
        strategy_bundle=strategy_bundle,
    )
    rules_defined = len(strategy_bundle.decision_rules) > 0

    context = strategy_bundle.strategic_context
    context_score = sum(
        1
        for item in [context.company, context.horizon, context.north_star_metric]
        if isinstance(item, str) and item.strip()
    ) / 3
    pillars_score = 1.0 if strategy_bundle.pillars else 0.0
    swot = strategy_bundle.swot
    swot_score = 0.0
    if swot:
        swot_score = (
            (1.0 if swot.strengths else 0.0)
            + (1.0 if swot.weaknesses else 0.0)
            + (1.0 if swot.opportunities else 0.0)
            + (1.0 if swot.threats else 0.0)
        ) / 4
    strategy_completeness = _clamp_01((context_score + pillars_score + swot_score) / 3)

    reconciliation_completeness = _clamp_01(1.0 - (len(coverage_gaps) / total_kpis)) if kpis_defined else 0.0

    scoring_weights = {
        "strategy_completeness": 0.15,
        "kpi_completeness": 0.2,
        "target_completeness": 0.15,
        "rule_completeness": 0.2,
        "reconciliation_completeness": 0.15,
        "data_readiness": 0.15,
    }
    total_weight = sum(scoring_weights.values()) or 1.0
    placeholders = []
    readiness_notes: list[str] = []
    if not kpis_defined:
        overall_score = 0.0
        placeholders.append("no_kpis_defined")
        explanation = (
            "No KPIs defined yet; readiness is preliminary. "
            "Add KPIs to enable KPI, target, reconciliation, and data readiness calculations."
        )
        readiness_notes.append("No KPIs defined yet; readiness remains preliminary.")
    else:
        overall_score = _clamp_01(
            (
                (strategy_completeness * scoring_weights["strategy_completeness"])
                + (kpi_completeness * scoring_weights["kpi_completeness"])
                + (target_completeness * scoring_weights["target_completeness"])
                + (rule_completeness * scoring_weights["rule_completeness"])
                + (reconciliation_completeness * scoring_weights["reconciliation_completeness"])
                + (data_readiness * scoring_weights["data_readiness"])
            )
            / total_weight
        )
        explanation = (
            f"Strategy completeness: {strategy_completeness:.2f}. "
            f"KPIs with full dependencies: {kpis_with_full_dependencies}/{total_kpis}. "
            f"Targets defined for KPIs: {kpis_with_targets}/{total_kpis}. "
            f"Missing columns: {missing_columns_total}/{required_columns_total or 0}. "
            f"Rule conditions validated: {valid_rules}/{len(strategy_bundle.decision_rules)}."
        )
        unresolved_count = len(coverage_gaps)
        if unresolved_count > 0:
            readiness_notes.append(f"{unresolved_count} KPI(s) have unresolved dependencies.")
        missing_targets_count = max(total_kpis - kpis_with_targets, 0)
        if missing_targets_count > 0:
            readiness_notes.append(f"{missing_targets_count} KPI(s) are missing targets.")
        if unknown_rule_references > 0:
            readiness_notes.append(f"{unknown_rule_references} rule reference(s) point to unavailable KPIs.")
        if not readiness_notes:
            readiness_notes.append("Readiness metrics are healthy with no critical structural gaps.")

    readiness = DecisionReadiness(
        overall_score=overall_score,
        strategy_completeness=strategy_completeness,
        kpi_completeness=kpi_completeness,
        target_completeness=target_completeness,
        rule_completeness=rule_completeness,
        reconciliation_completeness=reconciliation_completeness,
        data_readiness=data_readiness,
        explanation=explanation,
    )
    readiness_flags = ReadinessFlags(
        kpis_defined=kpis_defined,
        targets_defined=targets_defined,
        rules_defined=rules_defined,
        placeholders=placeholders,
    )

    summaries = {
        "dataset_id": schema_snapshot.dataset_id,
        "total_kpis": total_kpis,
        "kpis_with_full_dependencies": kpis_with_full_dependencies,
        "kpis_with_targets": kpis_with_targets,
        "missing_columns_total": missing_columns_total,
        "required_columns_total": required_columns_total,
        "rules_total": len(strategy_bundle.decision_rules),
        "rules_ready": valid_rules,
        "unknown_rule_references": unknown_rule_references,
        "available_marts": sorted(schema_snapshot.available_marts),
        "unavailable_marts": schema_snapshot.unavailable_marts,
        "notes": schema_snapshot.notes,
        "legacy_scoring_weights": _legacy_weights(strategy_bundle),
        "readiness_notes": readiness_notes,
    }
    return readiness, coverage_gaps, summaries, readiness_flags
