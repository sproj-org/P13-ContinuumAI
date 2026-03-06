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


def _heuristic_candidates(text: str, snapshot: DatasetSchemaSnapshot) -> tuple[list[dict[str, Any]], list[str]]:
    lowered = text.lower()
    available_columns = _available_columns(snapshot)
    candidates: list[dict[str, Any]] = []
    notes: list[str] = []

    def first_available(options: list[str], fallback: str) -> str:
        for option in options:
            if option in available_columns:
                return option
        return fallback

    if any(token in lowered for token in ("sales", "revenue", "net sales")):
        sales_col = first_available(["net_sales", "sales_amount", "revenue", "total_sales"], "net_sales")
        candidates.append(
            {
                "id": "total_sales",
                "display_name": "Total Sales",
                "description": "Total sales across selected marts.",
                "formula": f"sum({sales_col})",
                "required_columns": [sales_col],
                "pillar_id": "growth",
                "owner": "strategy_agent",
                "default_grain": "day",
            }
        )

    if any(token in lowered for token in ("transaction", "order count", "orders")):
        order_col = first_available(["order_id", "transaction_id"], "order_id")
        candidates.append(
            {
                "id": "transactions",
                "display_name": "Transactions",
                "description": "Count of distinct transactions.",
                "formula": f"count_distinct({order_col})",
                "required_columns": [order_col],
                "pillar_id": "growth",
                "owner": "strategy_agent",
                "default_grain": "day",
            }
        )

    if any(token in lowered for token in ("average order value", "aov")):
        sales_col = first_available(["net_sales", "sales_amount", "revenue"], "net_sales")
        order_col = first_available(["order_id", "transaction_id"], "order_id")
        candidates.append(
            {
                "id": "average_order_value",
                "display_name": "Average Order Value",
                "description": "Average value per order.",
                "formula": f"sum({sales_col}) / nullif(count_distinct({order_col}), 0)",
                "required_columns": [sales_col, order_col],
                "pillar_id": "growth",
                "owner": "strategy_agent",
                "default_grain": "day",
            }
        )

    if not candidates:
        fallback_column = "net_sales" if "net_sales" in available_columns else next(iter(available_columns), "id")
        candidates.append(
            {
                "id": "key_metric",
                "display_name": "Key Metric",
                "description": "Heuristic KPI candidate extracted from strategy notes.",
                "formula": f"sum({fallback_column})" if fallback_column != "id" else "count(*)",
                "required_columns": [] if fallback_column == "id" else [fallback_column],
                "pillar_id": "growth",
                "owner": "strategy_agent",
                "default_grain": "day",
            }
        )
        notes.append("No explicit KPI keywords found; returned a generic KPI candidate.")
    else:
        notes.append("Heuristic extraction generated KPI candidates from strategy text.")

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
        "You extract KPI candidates from business strategy notes. "
        "Return JSON with key 'candidates' as a list of KPI objects. "
        "Each KPI should include id, display_name, description, formula, marts, required_columns, "
        "dimensions, default_grain, pillar_id, owner. Keep output concise."
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
                    if close_matches:
                        suggestions.append(
                            {
                                "kpi_id": candidate["id"],
                                "mart": mart,
                                "missing_column": column,
                                "suggested_columns": close_matches,
                            }
                        )

    return {
        "reconciled": reconciled,
        "missing": missing,
        "suggestions": suggestions,
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
