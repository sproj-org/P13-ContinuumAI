"""Strategy evaluation service for KPI/target execution."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import re
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.kpi_registry import KPIRegistry
from app.models.strategy_bundle import DecisionRule, StrategyBundle, TargetThreshold
from app.services.strategy.evaluator import evaluate_kpi_formula
from app.services.strategy.schema_provider import load_dataset_schema
from app.services.strategy.storage import load_current_artifacts

KpiStatus = Literal["green", "yellow", "red", "no_target", "unavailable"]
_KPI_REF_RE = re.compile(r"""kpi\(\s*["']([^"']+)["']\s*\)""")
_TARGET_REF_RE = re.compile(r"""target\(\s*["']([^"']+)["']\s*\)""")


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


def _eval_expr_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_expr_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, bool)):
            return node.value
        raise ValueError("Unsupported constant")
    if isinstance(node, ast.UnaryOp):
        operand = _eval_expr_node(node.operand)
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.Not):
            return not bool(operand)
        raise ValueError("Unsupported unary operator")
    if isinstance(node, ast.BinOp):
        left = _eval_expr_node(node.left)
        right = _eval_expr_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        raise ValueError("Unsupported binary operator")
    if isinstance(node, ast.BoolOp):
        values = [_eval_expr_node(item) for item in node.values]
        if isinstance(node.op, ast.And):
            return all(bool(item) for item in values)
        if isinstance(node.op, ast.Or):
            return any(bool(item) for item in values)
        raise ValueError("Unsupported boolean operator")
    if isinstance(node, ast.Compare):
        left = _eval_expr_node(node.left)
        result = True
        for operator, comparator in zip(node.ops, node.comparators):
            right = _eval_expr_node(comparator)
            if isinstance(operator, ast.Lt):
                result = result and (left < right)
            elif isinstance(operator, ast.LtE):
                result = result and (left <= right)
            elif isinstance(operator, ast.Gt):
                result = result and (left > right)
            elif isinstance(operator, ast.GtE):
                result = result and (left >= right)
            elif isinstance(operator, ast.Eq):
                result = result and (left == right)
            elif isinstance(operator, ast.NotEq):
                result = result and (left != right)
            else:
                raise ValueError("Unsupported comparison operator")
            left = right
        return result
    raise ValueError(f"Unsupported expression node '{type(node).__name__}'")


def _replace_rule_references(
    condition: str,
    *,
    kpi_values: dict[str, float | None],
    targets: dict[str, TargetThreshold],
) -> tuple[str | None, str | None]:
    missing_references: list[str] = []

    def _replace_kpi(match: re.Match[str]) -> str:
        kpi_id = match.group(1).strip()
        value = kpi_values.get(kpi_id)
        if value is None:
            missing_references.append(f"kpi:{kpi_id}")
            return "0"
        return str(float(value))

    def _replace_target(match: re.Match[str]) -> str:
        kpi_id = match.group(1).strip()
        target = targets.get(kpi_id)
        if target is None:
            missing_references.append(f"target:{kpi_id}")
            return "0"
        return str(float(target.target))

    rendered = _KPI_REF_RE.sub(_replace_kpi, condition)
    rendered = _TARGET_REF_RE.sub(_replace_target, rendered)
    if missing_references:
        return None, ", ".join(sorted(set(missing_references)))
    return rendered, None


def evaluate_rule(
    *,
    rule: DecisionRule,
    kpi_values: dict[str, float | None],
    targets: dict[str, TargetThreshold],
) -> tuple[bool, str | None]:
    rendered, missing_reason = _replace_rule_references(rule.condition, kpi_values=kpi_values, targets=targets)
    if rendered is None:
        return False, f"missing_references:{missing_reason}"

    try:
        parsed = ast.parse(rendered, mode="eval")
        result = _eval_expr_node(parsed)
        return bool(result), None
    except Exception as exc:
        return False, f"invalid_expression:{type(exc).__name__}"


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
    kpi_values: dict[str, float | None] = {}
    targets = dict(strategy_bundle.targets)
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
        kpi_values[kpi.id] = value

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

    triggered_rules: list[dict[str, Any]] = []
    for rule in strategy_bundle.decision_rules:
        triggered, evaluation_error = evaluate_rule(
            rule=rule,
            kpi_values=kpi_values,
            targets=targets,
        )
        if not triggered:
            continue
        triggered_rules.append(
            {
                "id": rule.id,
                "condition": rule.condition,
                "action": rule.action,
                "severity": rule.severity,
                "rationale": rule.rationale,
                "evaluation_error": evaluation_error,
            }
        )

    return {
        "dataset_id": dataset_id,
        "revision": revision,
        "kpis": kpi_results,
        "triggered_rules": triggered_rules,
        "evaluation_time": datetime.now(timezone.utc).isoformat(),
    }
