"""StrategyAgent scaffolding for KPI extraction/reconciliation/apply."""

from __future__ import annotations

import difflib
import logging
import re
import uuid
from threading import RLock
from typing import Any

import yaml

from app.core.config import get_settings
from app.models.kpi_registry import KPIRegistry, KPIRegistryEntry
from app.models.strategy_bundle import DecisionRule, StrategyBundle, TargetThreshold
from app.services.llm.openai_client import OpenAIClient
from app.services.llm.openai_diagnostics import classify_openai_exception, log_openai_failure
from app.services.strategy.errors import StrategyRevisionConflictError, StrategyValidationError
from app.services.strategy.schema_provider import DatasetSchemaSnapshot, load_dataset_schema
from app.services.strategy.storage import (
    BASE_KPI_PATH,
    BASE_STRATEGY_PATH,
    commit_base_artifacts,
    get_current_revision_id,
    load_yaml,
    restore_revision_snapshot,
)

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ID_RE = re.compile(r"[^a-z0-9_]+")

_PATCH_CACHE: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
_PATCH_CACHE_LOCK = RLock()


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


def _load_base_registry_payload() -> dict[str, Any]:
    payload = load_yaml(BASE_KPI_PATH)
    if not payload:
        payload = {"schema_version": 1, "version": "1.0.0", "kpis": [], "aliases": {}, "derived_metrics": {}}
    payload.setdefault("kpis", [])
    payload.setdefault("aliases", {})
    payload.setdefault("derived_metrics", {})
    validated = KPIRegistry.model_validate(payload)
    return validated.model_dump(mode="python")


def _load_base_strategy_payload() -> dict[str, Any]:
    payload = load_yaml(BASE_STRATEGY_PATH)
    if not payload:
        raise StrategyValidationError("Strategy bundle is missing.")
    validated = StrategyBundle.model_validate(payload)
    return validated.model_dump(mode="python")


def _next_patch_id() -> str:
    return f"patch_{uuid.uuid4().hex[:12]}"


def _build_patch(
    *,
    patch_type: str,
    target_id: str,
    before: dict[str, Any] | None,
    after: dict[str, Any],
    rationale: str,
    confidence: float,
    source: str = "heuristic",
) -> dict[str, Any]:
    return {
        "patch_id": _next_patch_id(),
        "type": patch_type,
        "target_id": target_id,
        "before": before or {},
        "after": after,
        "rationale": rationale,
        "confidence": round(confidence, 2),
        "source": source,
    }


def _cache_patches(dataset_id: str, revision: str, patches: list[dict[str, Any]]) -> None:
    with _PATCH_CACHE_LOCK:
        key = (dataset_id, revision)
        _PATCH_CACHE[key] = {
            str(item.get("patch_id")): item
            for item in patches
            if isinstance(item, dict) and str(item.get("patch_id") or "").strip()
        }


def _resolve_cached_patches(dataset_id: str, revision: str, selected_patch_ids: list[str]) -> list[dict[str, Any]]:
    with _PATCH_CACHE_LOCK:
        patch_map = _PATCH_CACHE.get((dataset_id, revision), {})
    missing = [patch_id for patch_id in selected_patch_ids if patch_id not in patch_map]
    if missing:
        raise StrategyValidationError(
            f"Patch ids not available in current reconciliation cache: {', '.join(missing)}"
        )
    return [patch_map[patch_id] for patch_id in selected_patch_ids]


def reconcile_kpis(candidates: list[dict[str, Any]], dataset_schema: DatasetSchemaSnapshot) -> dict[str, Any]:
    reconciled: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []
    column_matches: list[dict[str, Any]] = []
    patches: list[dict[str, Any]] = []

    base_registry = _load_base_registry_payload()
    base_strategy = _load_base_strategy_payload()
    existing_kpi_ids = {
        str(item.get("id"))
        for item in base_registry.get("kpis", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    existing_rule_ids = {
        str(item.get("id"))
        for item in base_strategy.get("decision_rules", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    existing_targets = base_strategy.get("targets", {})
    if not isinstance(existing_targets, dict):
        existing_targets = {}

    alias_map = {
        "sales": ["net_sales", "sales_amount", "revenue"],
        "revenue": ["net_sales", "revenue", "sales_amount"],
        "orders": ["orders", "order_id", "transaction_id"],
        "transactions": ["orders", "transaction_id", "order_id"],
        "discount": ["discount_amount", "discount_ratio"],
        "returns": ["returns_amount", "return_rate_amount"],
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

        if candidate["id"] not in existing_kpi_ids:
            patches.append(
                _build_patch(
                    patch_type="add_kpi",
                    target_id=candidate["id"],
                    before={},
                    after={"kpi": candidate},
                    rationale="Candidate KPI can be added to registry.",
                    confidence=0.86 if status == "ready" else 0.62,
                )
            )

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
                        suggestions.append(match_payload)
                        column_matches.append(match_payload)
                        patches.append(
                            _build_patch(
                                patch_type="replace_column",
                                target_id=candidate["id"],
                                before={"column": column},
                                after={
                                    "kpi_id": candidate["id"],
                                    "mart": mart,
                                    "from_column": column,
                                    "to_column": close_matches[0],
                                },
                                rationale="Replace missing dependency with closest available column.",
                                confidence=0.7,
                            )
                        )

        if candidate["id"] not in existing_targets:
            patches.append(
                _build_patch(
                    patch_type="set_target",
                    target_id=candidate["id"],
                    before={},
                    after={
                        "target": {
                            "kpi_id": candidate["id"],
                            "target_value": 0.1,
                            "yellow_threshold": 0.07,
                            "red_threshold": 0.04,
                            "direction": "up",
                            "owner": candidate.get("owner") or "strategy",
                            "horizon": "FY2026",
                        }
                    },
                    rationale="Seed baseline target for KPI without existing target.",
                    confidence=0.6,
                )
            )

        rule_id = f"rule_{candidate['id']}_guardrail"
        if rule_id not in existing_rule_ids:
            patches.append(
                _build_patch(
                    patch_type="add_rule",
                    target_id=rule_id,
                    before={},
                    after={
                        "rule": {
                            "id": rule_id,
                            "condition": f'kpi(\"{candidate["id"]}\") < target(\"{candidate["id"]}\")',
                            "action": f"Review corrective plan for {candidate['id']}.",
                            "severity": "warn",
                            "rationale": "Auto-generated guardrail for candidate KPI.",
                        }
                    },
                    rationale="Add guardrail rule for KPI monitoring.",
                    confidence=0.55,
                )
            )

    return {
        "candidates": reconciled,
        "reconciled": reconciled,
        "missing": missing,
        "missing_dependencies": missing,
        "suggestions": suggestions,
        "column_matches": column_matches,
        "patches": patches,
    }


def _upsert_kpi_entry(kpi_payload: dict[str, Any], kpi_entry: dict[str, Any]) -> None:
    kpis = kpi_payload.get("kpis", [])
    if not isinstance(kpis, list):
        raise StrategyValidationError("KPI payload is invalid.")
    entry = KPIRegistryEntry.model_validate(kpi_entry).model_dump(mode="python", exclude_none=True)
    replaced = False
    for idx, item in enumerate(kpis):
        if isinstance(item, dict) and item.get("id") == entry["id"]:
            kpis[idx] = entry
            replaced = True
            break
    if not replaced:
        kpis.append(entry)
    kpi_payload["kpis"] = kpis


def _apply_patch_to_payloads(
    *,
    patch: dict[str, Any],
    base_strategy: dict[str, Any],
    base_kpi: dict[str, Any],
    schema_snapshot: DatasetSchemaSnapshot,
) -> None:
    patch_type = str(patch.get("type") or "").strip()
    target_id = str(patch.get("target_id") or "").strip()
    after = patch.get("after") or {}

    if patch_type == "add_kpi":
        candidate = after.get("kpi") if isinstance(after, dict) else None
        normalized = _normalize_candidate(candidate, schema_snapshot)
        if normalized:
            _upsert_kpi_entry(base_kpi, normalized)
        return

    if patch_type == "replace_column":
        details = after if isinstance(after, dict) else {}
        kpi_id = str(details.get("kpi_id") or target_id).strip()
        from_column = str(details.get("from_column") or "").strip()
        to_column = str(details.get("to_column") or "").strip()
        if not kpi_id or not from_column or not to_column:
            return
        kpis = base_kpi.get("kpis", [])
        if not isinstance(kpis, list):
            return
        for item in kpis:
            if not isinstance(item, dict) or item.get("id") != kpi_id:
                continue
            required_columns = item.get("required_columns", [])
            if isinstance(required_columns, list):
                item["required_columns"] = [to_column if col == from_column else col for col in required_columns]
            formula = str(item.get("formula") or "")
            if formula:
                item["formula"] = formula.replace(from_column, to_column)
            break
        return

    if patch_type == "update_formula":
        new_formula = str((after or {}).get("formula") or "").strip()
        if not target_id or not new_formula:
            return
        kpis = base_kpi.get("kpis", [])
        if not isinstance(kpis, list):
            return
        for item in kpis:
            if isinstance(item, dict) and item.get("id") == target_id:
                item["formula"] = new_formula
                break
        return

    if patch_type == "set_target":
        target_payload = (after or {}).get("target") if isinstance(after, dict) else None
        if not isinstance(target_payload, dict):
            return
        kpi_id = str(target_payload.get("kpi_id") or target_id).strip()
        if not kpi_id:
            return
        target = TargetThreshold(
            target=float(target_payload.get("target_value")),
            red_threshold=target_payload.get("red_threshold"),
            yellow_threshold=target_payload.get("yellow_threshold"),
            direction=str(target_payload.get("direction") or "up"),
            owner=target_payload.get("owner"),
            horizon=target_payload.get("horizon"),
        ).model_dump(mode="python", exclude_none=True)
        targets = base_strategy.get("targets", {})
        if not isinstance(targets, dict):
            targets = {}
        targets[kpi_id] = target
        base_strategy["targets"] = targets
        return

    if patch_type == "add_rule":
        rule_payload = (after or {}).get("rule") if isinstance(after, dict) else None
        if not isinstance(rule_payload, dict):
            return
        validated_rule = DecisionRule.model_validate(rule_payload).model_dump(mode="python", exclude_none=True)
        rules = base_strategy.get("decision_rules", [])
        if not isinstance(rules, list):
            rules = []
        if not any(isinstance(item, dict) and item.get("id") == validated_rule["id"] for item in rules):
            rules.append(validated_rule)
        base_strategy["decision_rules"] = rules
        return

    if patch_type == "legacy":
        op = str(patch.get("op") or "").strip()
        if op == "upsert_kpis":
            incoming = patch.get("kpis", [])
            if isinstance(incoming, list):
                for raw_item in incoming:
                    candidate = _normalize_candidate(raw_item, schema_snapshot)
                    if candidate:
                        _upsert_kpi_entry(base_kpi, candidate)
            return


def apply_selected_patches(
    *,
    dataset_id: str,
    selected_patch_ids: list[str],
    expected_revision: str,
    author: str,
    reason: str,
    explicit_patches: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if expected_revision != get_current_revision_id():
        raise StrategyRevisionConflictError("stale revision")

    selected_patches: list[dict[str, Any]] = []
    if explicit_patches:
        patch_map = {
            str(item.get("patch_id")): item
            for item in explicit_patches
            if isinstance(item, dict) and str(item.get("patch_id") or "").strip()
        }
        if selected_patch_ids:
            missing_ids = [patch_id for patch_id in selected_patch_ids if patch_id not in patch_map]
            if missing_ids:
                raise StrategyValidationError(
                    f"Selected patch ids not found in explicit payload: {', '.join(missing_ids)}"
                )
            selected_patches = [patch_map[item] for item in selected_patch_ids]
        else:
            selected_patches = list(patch_map.values())
    elif selected_patch_ids:
        selected_patches = _resolve_cached_patches(dataset_id, expected_revision, selected_patch_ids)

    if not selected_patches:
        raise StrategyValidationError("No patches selected for apply.")

    schema_snapshot = load_dataset_schema(dataset_id)
    base_strategy = _load_base_strategy_payload()
    base_kpi = _load_base_registry_payload()

    applied_ids: list[str] = []
    applied_types: list[str] = []
    for patch in selected_patches:
        _apply_patch_to_payloads(
            patch=patch,
            base_strategy=base_strategy,
            base_kpi=base_kpi,
            schema_snapshot=schema_snapshot,
        )
        patch_id = str(patch.get("patch_id") or "").strip()
        if patch_id:
            applied_ids.append(patch_id)
        applied_types.append(str(patch.get("type") or patch.get("op") or "unknown"))

    _, merged_kpi, new_revision = commit_base_artifacts(
        base_strategy_payload=base_strategy,
        base_kpi_payload=base_kpi,
        expected_revision=expected_revision,
        author=author,
        reason=reason,
    )

    return {
        "revision": new_revision,
        "previous_revision": expected_revision,
        "applied_summary": {
            "selected_patch_ids": applied_ids,
            "applied_patch_types": applied_types,
            "applied_count": len(applied_types),
            "kpi_count": len(merged_kpi.get("kpis", [])),
        },
    }


def apply_patch(
    *,
    dataset_id: str,
    patch: dict[str, Any],
    expected_revision: str,
    author: str,
    reason: str,
) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise StrategyValidationError("Patch payload must be an object.")

    # Backward-compatible single patch body.
    if "type" not in patch:
        legacy = dict(patch)
        legacy["type"] = "legacy"
        legacy["patch_id"] = legacy.get("patch_id") or _next_patch_id()
        return apply_selected_patches(
            dataset_id=dataset_id,
            selected_patch_ids=[str(legacy["patch_id"])],
            expected_revision=expected_revision,
            author=author,
            reason=reason,
            explicit_patches=[legacy],
        )

    patch_payload = dict(patch)
    patch_payload["patch_id"] = patch_payload.get("patch_id") or _next_patch_id()
    return apply_selected_patches(
        dataset_id=dataset_id,
        selected_patch_ids=[str(patch_payload["patch_id"])],
        expected_revision=expected_revision,
        author=author,
        reason=reason,
        explicit_patches=[patch_payload],
    )


def undo_patch(
    *,
    revision_to_restore: str,
    expected_revision: str,
    author: str,
    reason: str,
) -> dict[str, Any]:
    new_revision = restore_revision_snapshot(
        revision_to_restore=revision_to_restore,
        expected_revision=expected_revision,
        author=author,
        reason=reason,
    )
    return {
        "revision": new_revision,
        "restored_from_revision": revision_to_restore,
    }


def cache_reconcile_patches(dataset_id: str, revision: str, patches: list[dict[str, Any]]) -> None:
    _cache_patches(dataset_id, revision, patches)
