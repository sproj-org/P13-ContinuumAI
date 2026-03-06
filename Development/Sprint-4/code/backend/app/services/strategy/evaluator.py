"""KPI formula evaluation engine for Strategy execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.query import AggregateFilter, AggregateRequest, AggregateSpec, execute_aggregate_request
from app.models.kpi_registry import KPIRegistryEntry
from app.services.strategy.schema_provider import DatasetSchemaSnapshot, load_dataset_schema

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_AGG_CALL_RE = re.compile(r"^(sum|count|avg)\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)$", re.IGNORECASE)
_DIVISION_RE = re.compile(
    r"^(sum|count|avg)\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*/\s*(sum|count|avg)\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)$",
    re.IGNORECASE,
)
_NULLIF_DIVISION_RE = re.compile(
    r"^(sum|count|avg)\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*/\s*nullif\(\s*(sum|count|avg)\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*,\s*0\s*\)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AggregationTerm:
    fn: Literal["sum", "count", "avg"]
    column: str


@dataclass(frozen=True)
class FormulaPlan:
    formula_type: Literal["single", "division"]
    numerator: AggregationTerm
    denominator: AggregationTerm | None = None
    safe_divide: bool = False

    @property
    def required_columns(self) -> set[str]:
        columns = {self.numerator.column}
        if self.denominator is not None:
            columns.add(self.denominator.column)
        return columns


def _normalize_identifier(value: str) -> str:
    candidate = value.strip()
    if not _IDENTIFIER_RE.match(candidate):
        raise ValueError(f"Invalid identifier '{value}'")
    return candidate


def parse_formula(formula: str) -> FormulaPlan:
    text = formula.strip()
    if not text:
        raise ValueError("Formula is required")

    single_match = _AGG_CALL_RE.match(text)
    if single_match:
        fn, column = single_match.groups()
        return FormulaPlan(
            formula_type="single",
            numerator=AggregationTerm(fn=fn.lower(), column=_normalize_identifier(column)),
        )

    nullif_division_match = _NULLIF_DIVISION_RE.match(text)
    if nullif_division_match:
        n_fn, n_col, d_fn, d_col = nullif_division_match.groups()
        return FormulaPlan(
            formula_type="division",
            numerator=AggregationTerm(fn=n_fn.lower(), column=_normalize_identifier(n_col)),
            denominator=AggregationTerm(fn=d_fn.lower(), column=_normalize_identifier(d_col)),
            safe_divide=True,
        )

    division_match = _DIVISION_RE.match(text)
    if division_match:
        n_fn, n_col, d_fn, d_col = division_match.groups()
        return FormulaPlan(
            formula_type="division",
            numerator=AggregationTerm(fn=n_fn.lower(), column=_normalize_identifier(n_col)),
            denominator=AggregationTerm(fn=d_fn.lower(), column=_normalize_identifier(d_col)),
            safe_divide=False,
        )

    raise ValueError(
        "Unsupported formula syntax. Supported patterns: "
        "sum(col), count(col), avg(col), sum(col1)/sum(col2), sum(col)/nullif(sum(col2),0)"
    )


def _build_aggregate_filters(
    *,
    filters: list[dict[str, Any]] | None,
    time_range: dict[str, Any] | None,
) -> list[AggregateFilter]:
    output: list[AggregateFilter] = []
    for item in filters or []:
        if not isinstance(item, dict):
            continue
        output.append(AggregateFilter.model_validate(item))

    if isinstance(time_range, dict):
        column = str(time_range.get("column") or "").strip()
        if column:
            start = time_range.get("from")
            end = time_range.get("to")
            if start is not None:
                output.append(AggregateFilter(column=column, op="gte", value=start))
            if end is not None:
                output.append(AggregateFilter(column=column, op="lte", value=end))
    return output


def _extract_single_value(payload: dict[str, Any]) -> float | None:
    rows = payload.get("rows", [])
    if not isinstance(rows, list) or not rows:
        return None
    first = rows[0]
    if not isinstance(first, dict):
        return None
    value = first.get("agg_value")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _choose_mart_for_kpi(
    *,
    kpi: KPIRegistryEntry,
    schema_snapshot: DatasetSchemaSnapshot,
    required_columns: set[str],
) -> str | None:
    candidate_marts = list(kpi.marts or [])
    if not candidate_marts:
        candidate_marts = sorted(schema_snapshot.available_marts)

    for mart in candidate_marts:
        if mart not in schema_snapshot.available_marts:
            continue
        available_cols = schema_snapshot.mart_columns.get(mart, set())
        if required_columns.issubset(available_cols):
            return mart
    return None


def build_query_spec(
    *,
    mart: str,
    plan: FormulaPlan,
    filters: list[AggregateFilter],
    dimensions: list[str] | None,
) -> dict[str, Any]:
    aggregations: list[dict[str, Any]] = [
        {"fn": plan.numerator.fn, "column": plan.numerator.column},
    ]
    if plan.denominator is not None:
        aggregations.append({"fn": plan.denominator.fn, "column": plan.denominator.column})

    return {
        "mart": mart,
        "aggregations": aggregations,
        "filters": [item.model_dump(mode="python") for item in filters],
        "dimensions": list(dimensions or []),
    }


def _execute_aggregation(
    *,
    dataset_id: str,
    mart: str,
    aggregation: AggregationTerm,
    filters: list[AggregateFilter],
    db: Session,
) -> float | None:
    request = AggregateRequest(
        table_name=mart,
        group_by=[],
        filters=filters,
        agg=AggregateSpec(fn=aggregation.fn, column=aggregation.column),
        limit=1,
    )
    payload = execute_aggregate_request(dataset_id=dataset_id, request=request, db=db)
    return _extract_single_value(payload)


def validate_formula_columns(
    *,
    dataset_id: str,
    mart: str,
    required_columns: set[str],
    schema_snapshot: DatasetSchemaSnapshot | None = None,
) -> tuple[bool, list[str]]:
    snapshot = schema_snapshot or load_dataset_schema(dataset_id)
    available = snapshot.mart_columns.get(mart, set())
    missing = sorted([column for column in required_columns if column not in available])
    return len(missing) == 0, missing


def evaluate_kpi_formula(
    *,
    dataset_id: str,
    kpi: KPIRegistryEntry,
    db: Session,
    filters: list[dict[str, Any]] | None = None,
    time_range: dict[str, Any] | None = None,
    schema_snapshot: DatasetSchemaSnapshot | None = None,
) -> dict[str, Any]:
    snapshot = schema_snapshot or load_dataset_schema(dataset_id)
    provenance: dict[str, Any] = {
        "formula": kpi.formula,
        "mart": None,
        "query_spec": None,
        "execution": [],
        "errors": [],
    }

    try:
        plan = parse_formula(kpi.formula)
    except ValueError as exc:
        provenance["errors"].append(str(exc))
        return {"value": None, "provenance": provenance}

    required_columns = set(kpi.required_columns or []) | plan.required_columns
    mart = _choose_mart_for_kpi(kpi=kpi, schema_snapshot=snapshot, required_columns=required_columns)
    if mart is None:
        provenance["errors"].append("No mart contains the required columns for this KPI formula.")
        return {"value": None, "provenance": provenance}

    valid, missing_columns = validate_formula_columns(
        dataset_id=dataset_id,
        mart=mart,
        required_columns=required_columns,
        schema_snapshot=snapshot,
    )
    if not valid:
        provenance["mart"] = mart
        provenance["errors"].append(f"Missing columns in mart '{mart}': {', '.join(missing_columns)}")
        return {"value": None, "provenance": provenance}

    try:
        agg_filters = _build_aggregate_filters(filters=filters, time_range=time_range)
    except Exception as exc:
        provenance["mart"] = mart
        provenance["errors"].append(f"Invalid filters/time_range: {exc}")
        return {"value": None, "provenance": provenance}

    query_spec = build_query_spec(
        mart=mart,
        plan=plan,
        filters=agg_filters,
        dimensions=list(kpi.dimensions or []),
    )
    provenance["mart"] = mart
    provenance["query_spec"] = query_spec

    try:
        numerator_value = _execute_aggregation(
            dataset_id=dataset_id,
            mart=mart,
            aggregation=plan.numerator,
            filters=agg_filters,
            db=db,
        )
        provenance["execution"].append(
            {
                "fn": plan.numerator.fn,
                "column": plan.numerator.column,
                "value": numerator_value,
            }
        )
        if plan.formula_type == "single":
            return {"value": numerator_value, "provenance": provenance}

        if plan.denominator is None:
            provenance["errors"].append("Invalid formula plan: missing denominator.")
            return {"value": None, "provenance": provenance}

        denominator_value = _execute_aggregation(
            dataset_id=dataset_id,
            mart=mart,
            aggregation=plan.denominator,
            filters=agg_filters,
            db=db,
        )
        provenance["execution"].append(
            {
                "fn": plan.denominator.fn,
                "column": plan.denominator.column,
                "value": denominator_value,
            }
        )

        if denominator_value in (None, 0.0):
            if plan.safe_divide:
                provenance["errors"].append("Division skipped due to zero/empty denominator (nullif safety).")
                return {"value": None, "provenance": provenance}
            provenance["errors"].append("Division by zero/empty denominator.")
            return {"value": None, "provenance": provenance}

        if numerator_value is None:
            provenance["errors"].append("Numerator evaluated to null.")
            return {"value": None, "provenance": provenance}

        return {"value": float(numerator_value) / float(denominator_value), "provenance": provenance}
    except HTTPException as exc:
        provenance["errors"].append(f"Aggregate execution error: {exc.detail}")
        return {"value": None, "provenance": provenance}
    except Exception as exc:
        provenance["errors"].append(f"Evaluation error: {type(exc).__name__}")
        return {"value": None, "provenance": provenance}
