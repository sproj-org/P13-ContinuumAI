"""StrategyAgent scaffolding for KPI extraction/reconciliation/apply."""

from __future__ import annotations

import difflib
import logging
import re
from typing import Any

import yaml

from app.core.config import get_settings
from app.models.kpi_registry import KPIRegistry, KPIRegistryEntry
from app.services.llm.openai_client import OpenAIClient
from app.services.llm.openai_diagnostics import classify_openai_exception, log_openai_failure
from app.services.strategy.errors import StrategyRevisionConflictError, StrategyValidationError
from app.services.strategy.schema_provider import DatasetSchemaSnapshot, load_dataset_schema
from app.services.strategy.storage import BASE_KPI_PATH, get_current_revision_id, load_yaml, update_kpi_registry

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ID_RE = re.compile(r"[^a-z0-9_]+")


def _normalize_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        trimmed = item.strip()
        if trimmed:
            output.append(trimmed)
    return output


def _slugify_identifier(value: str) -> str:
    normalized = _ID_RE.sub("_", value.strip().lower()).strip("_")
    return normalized or "kpi_metric"


def _available_columns(snapshot: DatasetSchemaSnapshot) -> set[str]:
    all_columns: set[str] = set()
    for columns in snapshot.mart_columns.values():
        all_columns.update(columns)
    return all_columns


def _infer_required_columns_from_formula(formula: str, available_columns: set[str]) -> list[str]:
    identifiers = [token for token in _TOKEN_RE.findall(formula) if token in available_columns]
    seen: set[str] = set()
    ordered: list[str] = []
    for identifier in identifiers:
        if identifier in seen:
            continue
        seen.add(identifier)
        ordered.append(identifier)
    return ordered


def _infer_marts(required_columns: list[str], snapshot: DatasetSchemaSnapshot) -> list[str]:
    if not required_columns:
        return sorted(snapshot.available_marts)

    strict = [
        mart_id
        for mart_id, columns in snapshot.mart_columns.items()
        if all(column in columns for column in required_columns)
    ]
    if strict:
        return sorted(strict)

    partial = [
        mart_id
        for mart_id, columns in snapshot.mart_columns.items()
        if any(column in columns for column in required_columns)
    ]
    return sorted(partial)


def _normalize_candidate(raw: Any, snapshot: DatasetSchemaSnapshot) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    available_columns = _available_columns(snapshot)
    display_name = str(raw.get("display_name") or "").strip() or None
    description = str(raw.get("description") or "").strip()
    fallback_name = display_name or description or str(raw.get("id") or "")
    candidate_id = _slugify_identifier(str(raw.get("id") or fallback_name or "kpi_metric"))
    formula = str(raw.get("formula") or "").strip()
    if not formula:
        formula = "sum(net_sales)" if "net_sales" in available_columns else "count(*)"

    required_columns = _normalize_text_list(raw.get("required_columns"))
    if not required_columns:
        required_columns = _infer_required_columns_from_formula(formula, available_columns)
    if not required_columns and "net_sales" in available_columns:
        required_columns = ["net_sales"]

    marts = [mart for mart in _normalize_text_list(raw.get("marts")) if mart in snapshot.available_marts]
    if not marts:
        marts = _infer_marts(required_columns, snapshot)
    if not marts and snapshot.available_marts:
        marts = [sorted(snapshot.available_marts)[0]]

    if not description:
        description = display_name or candidate_id.replace("_", " ").title()

    dimensions = _normalize_text_list(raw.get("dimensions"))
    default_grain = str(raw.get("default_grain") or "").strip() or None
    pillar_id = str(raw.get("pillar_id") or "").strip() or None
    owner = str(raw.get("owner") or "").strip() or None

    normalized: dict[str, Any] = {
        "id": candidate_id,
        "description": description,
        "formula": formula,
        "marts": marts,
        "required_columns": required_columns,
        "dimensions": dimensions,
        "default_grain": default_grain,
        "pillar_id": pillar_id,
        "owner": owner,
        "display_name": display_name,
    }
    return normalized


def _first_matching_column(available_columns: set[str], preferred_names: list[str]) -> str | None:
    for name in preferred_names:
        if name in available_columns:
            return name
    return None


def _find_column_by_keywords(available_columns: set[str], keywords: list[str]) -> str | None:
    lowered_map = {column.lower(): column for column in available_columns}
    for key in keywords:
        key_lower = key.lower()
        for lowered_name, original in lowered_map.items():
            if key_lower in lowered_name:
                return original
    return None


def _best_column(available_columns: set[str], preferred_names: list[str], keywords: list[str]) -> str | None:
    return _first_matching_column(available_columns, preferred_names) or _find_column_by_keywords(available_columns, keywords)


def _heuristic_candidates(text: str, snapshot: DatasetSchemaSnapshot) -> tuple[list[dict[str, Any]], list[str]]:
    lowered = text.lower()
    available_columns = _available_columns(snapshot)
    candidates: list[dict[str, Any]] = []
    notes: list[str] = []

    sales_col = _best_column(
        available_columns,
        ["net_sales", "sales_amount", "revenue", "total_sales"],
        ["sales", "revenue", "amount"],
    )
    order_col = _best_column(
        available_columns,
        ["order_id", "transaction_id"],
        ["order", "transaction"],
    )
    customer_col = _best_column(
        available_columns,
        ["customer_id", "client_id"],
        ["customer", "client"],
    )

    intent_specs = [
        {
            "intent_id": "total_sales",
            "keywords": ["sales", "revenue", "net sales"],
            "required": [sales_col],
            "formula": lambda: f"sum({sales_col})" if sales_col else "count(*)",
            "description": "Total sales across selected marts.",
        },
        {
            "intent_id": "transactions",
            "keywords": ["transaction", "order count", "orders"],
            "required": [order_col],
            "formula": lambda: f"count({order_col})" if order_col else "count(*)",
            "description": "Total transaction volume.",
        },
        {
            "intent_id": "average_basket_value",
            "keywords": ["avg basket", "average basket", "average order value", "aov"],
            "required": [sales_col, order_col],
            "formula": lambda: (
                f"sum({sales_col}) / nullif(count({order_col}), 0)"
                if sales_col and order_col
                else "count(*)"
            ),
            "description": "Average basket value per order.",
        },
        {
            "intent_id": "active_customers",
            "keywords": ["active customers", "customer count"],
            "required": [customer_col],
            "formula": lambda: f"count_distinct({customer_col})" if customer_col else "count(*)",
            "description": "Distinct customer count.",
        },
    ]

    matched_intents = [item for item in intent_specs if any(token in lowered for token in item["keywords"])]
    for intent in matched_intents:
        required_columns = [item for item in intent["required"] if item]
        marts = _infer_marts(required_columns, snapshot)
        candidates.append(
            {
                "id": intent["intent_id"],
                "display_name": intent["intent_id"].replace("_", " ").title(),
                "description": intent["description"],
                "formula": intent["formula"](),
                "required_columns": required_columns,
                "marts": marts,
                "pillar_id": "growth",
                "owner": "strategy_agent",
                "default_grain": "day",
            }
        )

    if not candidates:
        fallback_column = sales_col or order_col or customer_col or next(iter(available_columns), "id")
        fallback_formula = f"sum({fallback_column})" if fallback_column in available_columns else "count(*)"
        fallback_required = [fallback_column] if fallback_column in available_columns else []
        fallback_marts = _infer_marts(fallback_required, snapshot)
        candidates.append(
            {
                "id": "key_metric",
                "display_name": "Key Metric",
                "description": "Heuristic KPI candidate extracted from strategy notes.",
                "formula": fallback_formula,
                "required_columns": fallback_required,
                "marts": fallback_marts,
                "pillar_id": "growth",
                "owner": "strategy_agent",
                "default_grain": "day",
            }
        )
        notes.append("No explicit KPI keywords found; returned a generic KPI candidate.")
    else:
        notes.append("Heuristic extraction pipeline matched KPI intents from strategy text.")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in candidates:
        parsed = _normalize_candidate(item, snapshot)
        if parsed is None:
            continue
        if parsed["id"] in seen_ids:
            continue
        seen_ids.add(parsed["id"])
        normalized.append(parsed)

    return normalized, notes


def _openai_extract_candidates(text: str, snapshot: DatasetSchemaSnapshot) -> tuple[list[dict[str, Any]] | None, list[str]]:
    settings = get_settings()
    api_key = (settings.OPENAI_API_KEY or "").strip()
    if not api_key:
        return None, ["OpenAI is not configured; used heuristic extraction."]

    schema_lines = [
        f"- {mart_id}: {', '.join(sorted(columns)) or '(no columns)'}"
        for mart_id, columns in sorted(snapshot.mart_columns.items(), key=lambda item: item[0])
    ]
    system_prompt = (
        "You extract KPI candidates from business strategy notes.\n"
        "Use this deterministic pipeline: keyword detection -> column matching -> mart inference -> formula suggestion.\n"
        "Return strict JSON object with key 'candidates' as a list.\n"
        "Each candidate must include: id, display_name, description, formula, marts, required_columns, "
        "dimensions, default_grain, pillar_id, owner.\n"
        "Only use columns that exist in the provided schema and avoid free-form prose."
    )
    user_prompt = (
        "Dataset schema:\n"
        + "\n".join(schema_lines)
        + "\n\nStrategy notes:\n"
        + text[:6000]
    )

    try:
        client = OpenAIClient(api_key=api_key, model=settings.OPENAI_MODEL)
        payload = client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        raw_candidates = payload.get("candidates")
        if not isinstance(raw_candidates, list):
            return None, ["OpenAI response missing 'candidates'; used heuristic extraction."]

        normalized: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for raw in raw_candidates:
            parsed = _normalize_candidate(raw, snapshot)
            if parsed is None:
                continue
            if parsed["id"] in seen_ids:
                continue
            seen_ids.add(parsed["id"])
            normalized.append(parsed)

        if not normalized:
            return None, ["OpenAI returned no valid KPI candidates; used heuristic extraction."]
        return normalized, ["OpenAI-assisted extraction generated KPI candidates."]
    except Exception as exc:  # pragma: no cover - exercised in integration environments
        diagnostics = classify_openai_exception(exc)
        log_openai_failure(
            logger,
            "strategy_agent_extract",
            diagnostics,
            exception_class_name=type(exc).__name__,
        )
        return None, [f"OpenAI extraction failed ({diagnostics.get('openai_error_type')}); used heuristic extraction."]


def extract_kpis_from_text(text: str, dataset_id: str) -> dict[str, Any]:
    snapshot = load_dataset_schema(dataset_id)
    candidates, notes = _openai_extract_candidates(text, snapshot)
    if not candidates:
        candidates, heuristic_notes = _heuristic_candidates(text, snapshot)
        notes.extend(heuristic_notes)

    suggested_patch = {"op": "upsert_kpis", "kpis": candidates}
    return {
        "candidates": candidates,
        "notes": notes,
        "suggested_patches": [suggested_patch],
    }


def reconcile_kpis(candidates: list[dict[str, Any]], dataset_schema: DatasetSchemaSnapshot) -> dict[str, Any]:
    reconciled: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []
    column_matches: list[dict[str, Any]] = []

    alias_map = {
        "sales": ["net_sales", "sales_amount", "revenue"],
        "revenue": ["net_sales", "revenue", "sales_amount"],
        "orders": ["order_id", "transaction_id"],
        "transactions": ["transaction_id", "order_id"],
    }

    for raw in candidates:
        candidate = _normalize_candidate(raw, dataset_schema)
        if candidate is None:
            continue

        missing_marts = [mart for mart in candidate["marts"] if mart not in dataset_schema.available_marts]
        missing_columns_by_mart: dict[str, list[str]] = {}
        for mart in candidate["marts"]:
            available = dataset_schema.mart_columns.get(mart, set())
            missing_columns = [column for column in candidate["required_columns"] if column not in available]
            if missing_columns:
                missing_columns_by_mart[mart] = missing_columns

        status = "ready" if not missing_marts and not missing_columns_by_mart else "missing_dependencies"
        candidate_with_status = dict(candidate)
        candidate_with_status["status"] = status
        reconciled.append(candidate_with_status)

        if status != "ready":
            missing_item = {
                "kpi_id": candidate["id"],
                "reason": "missing_dependencies",
                "details": {
                    "missing_marts": missing_marts,
                    "missing_columns_by_mart": missing_columns_by_mart,
                },
            }
            missing.append(missing_item)

            for mart, columns in missing_columns_by_mart.items():
                available = sorted(dataset_schema.mart_columns.get(mart, set()))
                for column in columns:
                    close_matches = difflib.get_close_matches(column, available, n=3, cutoff=0.6)
                    lowered = column.lower()
                    if not close_matches:
                        for alias_key, alias_targets in alias_map.items():
                            if alias_key in lowered:
                                close_matches = [item for item in alias_targets if item in available]
                                if close_matches:
                                    break
                    if close_matches:
                        match_payload = {
                            "kpi_id": candidate["id"],
                            "mart": mart,
                            "missing_column": column,
                            "suggested_columns": close_matches,
                        }
                        suggestions.append(
                            match_payload
                        )
                        column_matches.append(match_payload)

    return {
        "candidates": reconciled,
        "reconciled": reconciled,
        "missing": missing,
        "missing_dependencies": missing,
        "suggestions": suggestions,
        "column_matches": column_matches,
    }


def _load_base_registry_payload() -> dict[str, Any]:
    payload = load_yaml(BASE_KPI_PATH)
    if not payload:
        payload = {"schema_version": 1, "version": "1.0.0", "kpis": [], "aliases": {}, "derived_metrics": {}}
    payload.setdefault("kpis", [])
    payload.setdefault("aliases", {})
    payload.setdefault("derived_metrics", {})
    validated = KPIRegistry.model_validate(payload)
    return validated.model_dump(mode="python")


def apply_patch(
    *,
    dataset_id: str,
    patch: dict[str, Any],
    expected_revision: str,
    author: str,
    reason: str,
) -> dict[str, Any]:
    if expected_revision != get_current_revision_id():
        raise StrategyRevisionConflictError("stale revision")

    if not isinstance(patch, dict):
        raise StrategyValidationError("Patch payload must be an object.")

    op = str(patch.get("op") or "upsert_kpis").strip()
    if not op:
        raise StrategyValidationError("Patch op is required.")

    schema_snapshot = load_dataset_schema(dataset_id)
    payload = _load_base_registry_payload()
    current_kpis = payload.get("kpis", [])
    if not isinstance(current_kpis, list):
        raise StrategyValidationError("KPI registry payload is invalid.")

    kpi_map: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in current_kpis:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            continue
        kpi_map[item_id] = item
        order.append(item_id)

    upserted: list[str] = []
    deleted: list[str] = []

    if op == "upsert_kpis":
        incoming = patch.get("kpis", [])
        if not isinstance(incoming, list):
            raise StrategyValidationError("Patch field 'kpis' must be a list.")

        for raw_item in incoming:
            candidate = _normalize_candidate(raw_item, schema_snapshot)
            if candidate is None:
                continue
            validated_entry = KPIRegistryEntry.model_validate(candidate).model_dump(mode="python", exclude_none=True)
            entry_id = validated_entry["id"]
            if entry_id not in kpi_map:
                order.append(entry_id)
            kpi_map[entry_id] = validated_entry
            upserted.append(entry_id)
    elif op == "delete_kpis":
        to_delete = patch.get("kpi_ids", [])
        if not isinstance(to_delete, list):
            raise StrategyValidationError("Patch field 'kpi_ids' must be a list.")
        for item in to_delete:
            if not isinstance(item, str):
                continue
            kpi_id = item.strip()
            if not kpi_id:
                continue
            if kpi_id in kpi_map:
                kpi_map.pop(kpi_id, None)
                deleted.append(kpi_id)
    else:
        raise StrategyValidationError(f"Unsupported patch op '{op}'.")

    payload["kpis"] = [kpi_map[kpi_id] for kpi_id in order if kpi_id in kpi_map]
    validated_payload = KPIRegistry.model_validate(payload).model_dump(mode="python")
    raw_yaml = yaml.safe_dump(validated_payload, sort_keys=False, allow_unicode=False)

    merged_registry, new_revision = update_kpi_registry(
        mode="base",
        raw_yaml=raw_yaml,
        expected_revision=expected_revision,
        author=author,
        reason=reason,
    )

    return {
        "revision": new_revision,
        "applied_summary": {
            "op": op,
            "upserted_kpis": sorted(set(upserted)),
            "deleted_kpis": sorted(set(deleted)),
            "kpi_count": len(merged_registry.get("kpis", [])),
        },
    }


def undo_patch(patch_id: str) -> dict[str, Any]:
    return {"status": "not_implemented", "patch_id": patch_id}
