"""Safe formula compilation and period-series evaluation for KPI expressions."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from app.services.intelligence.data_access import aggregate_time_series
from app.services.intelligence.specs import MetricAggregation, TimeGrain

_AGG_CALL_RE = re.compile(r"(?i)(sum|count|avg|min|max)\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)")
_ALLOWED_BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
_ALLOWED_UNARY_OPS = (ast.UAdd, ast.USub)


@dataclass(frozen=True)
class FormulaAggregationTerm:
    placeholder: str
    fn: MetricAggregation
    column: str


@dataclass(frozen=True)
class CompiledFormulaExpression:
    source: str
    rewritten: str
    tree: ast.Expression
    terms: tuple[FormulaAggregationTerm, ...]

    @property
    def required_columns(self) -> list[str]:
        output: list[str] = []
        for term in self.terms:
            if term.column not in output:
                output.append(term.column)
        return output


def _validate_ast(node: ast.AST, *, allowed_names: set[str]) -> None:
    if isinstance(node, ast.Expression):
        _validate_ast(node.body, allowed_names=allowed_names)
        return
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BIN_OPS):
        _validate_ast(node.left, allowed_names=allowed_names)
        _validate_ast(node.right, allowed_names=allowed_names)
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARY_OPS):
        _validate_ast(node.operand, allowed_names=allowed_names)
        return
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "nullif" and len(node.args) == 2:
        for argument in node.args:
            _validate_ast(argument, allowed_names=allowed_names)
        return
    if isinstance(node, ast.Name) and node.id in allowed_names:
        return
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return
    raise ValueError("Unsupported KPI formula expression for predictive analysis")


def compile_formula_expression(formula: str) -> CompiledFormulaExpression:
    source = re.sub(r"(?i)\bnullif\s*\(", "nullif(", formula.strip())
    if not source:
        raise ValueError("Formula is required")

    terms: list[FormulaAggregationTerm] = []
    term_lookup: dict[tuple[str, str], str] = {}

    def _replace(match: re.Match[str]) -> str:
        fn = str(match.group(1)).lower()
        column = str(match.group(2))
        key = (fn, column)
        placeholder = term_lookup.get(key)
        if placeholder is None:
            placeholder = f"agg_{len(terms)}"
            term_lookup[key] = placeholder
            terms.append(FormulaAggregationTerm(placeholder=placeholder, fn=fn, column=column))
        return placeholder

    rewritten = _AGG_CALL_RE.sub(_replace, source)
    tree = ast.parse(rewritten, mode="eval")
    _validate_ast(tree, allowed_names={term.placeholder for term in terms})
    return CompiledFormulaExpression(source=source, rewritten=rewritten, tree=tree, terms=tuple(terms))


def required_formula_columns(formula: str) -> list[str]:
    return compile_formula_expression(formula).required_columns


def _safe_nullif(left: Any, right: Any) -> Any:
    if isinstance(left, pd.Series) or isinstance(right, pd.Series):
        left_series = left if isinstance(left, pd.Series) else pd.Series([left] * len(right), index=right.index)
        right_series = right if isinstance(right, pd.Series) else pd.Series([right] * len(left_series), index=left_series.index)
        return left_series.where(left_series != right_series)
    return None if left == right else left


def _evaluate_node(node: ast.AST, *, scope: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _evaluate_node(node.body, scope=scope)
    if isinstance(node, ast.Name):
        return scope[node.id]
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.UnaryOp):
        operand = _evaluate_node(node.operand, scope=scope)
        return operand if isinstance(node.op, ast.UAdd) else -operand
    if isinstance(node, ast.BinOp):
        left = _evaluate_node(node.left, scope=scope)
        right = _evaluate_node(node.right, scope=scope)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            with np.errstate(divide="ignore", invalid="ignore"):
                return left / right
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "nullif":
        left = _evaluate_node(node.args[0], scope=scope)
        right = _evaluate_node(node.args[1], scope=scope)
        return _safe_nullif(left, right)
    raise ValueError("Unsupported KPI formula expression for predictive analysis")


def build_formula_time_series(
    frame: pd.DataFrame,
    *,
    time_field: str,
    formula: str,
    grain: TimeGrain,
    group_by: list[str] | None = None,
) -> pd.DataFrame:
    compiled = compile_formula_expression(formula)
    merged: pd.DataFrame | None = None
    key_columns = ["period_start", "period_label", *(group_by or [])]

    for term in compiled.terms:
        term_frame = aggregate_time_series(
            frame,
            time_field=time_field,
            metric=term.column,
            aggregation=term.fn,
            grain=grain,
            group_by=group_by,
        )
        if term_frame.empty:
            continue
        renamed = term_frame.rename(columns={"value": term.placeholder})
        merged = renamed if merged is None else merged.merge(renamed, on=key_columns, how="outer")

    if merged is None or merged.empty:
        return pd.DataFrame(columns=["period_start", "period_label", "value", *(group_by or [])])

    value = _evaluate_node(
        compiled.tree,
        scope={term.placeholder: pd.to_numeric(merged.get(term.placeholder), errors="coerce") for term in compiled.terms},
    )
    merged["value"] = pd.to_numeric(value, errors="coerce").replace([np.inf, -np.inf], np.nan)
    merged = merged.dropna(subset=["value"])
    if merged.empty:
        return pd.DataFrame(columns=["period_start", "period_label", "value", *(group_by or [])])
    return merged.sort_values(key_columns).reset_index(drop=True)
