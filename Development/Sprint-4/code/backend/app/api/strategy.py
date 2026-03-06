"""Dataset-scoped strategy API routes."""

from __future__ import annotations

import re
from typing import Any
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
import yaml

from app.core.mart_registry import DEFAULT_DATASET_ID
from app.core.security import get_current_user
from app.db.models import User
from app.models.kpi_registry import KPIRegistry, KPIRegistryEntry
from app.models.strategy_bundle import (
    SWOTBlock,
    StrategicContext,
    StrategyBundle,
    StrategyPillar,
    TargetThreshold,
)
from app.services.strategy.errors import (
    StrategyNotFoundError,
    StrategyRevisionConflictError,
    StrategyValidationError,
    StrategyYamlParseError,
)
from app.services.strategy import storage as strategy_storage
from app.services.strategy.storage import (
    get_current_revision_id,
    get_strategy_yaml_texts,
    load_current_artifacts,
    update_kpi_registry,
    update_strategy_bundle,
)
from app.services.strategy.schema_provider import load_dataset_schema
from app.services.strategy.store import get_strategy_store

router = APIRouter(prefix="/strategy", tags=["strategy"])
bundle_router = APIRouter(prefix="/strategy", tags=["strategy"])


def _require_bundle(dataset_id: str):
    store = get_strategy_store()
    try:
        return store.load_bundle(dataset_id)
    except StrategyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StrategyValidationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _raise_error(
    *,
    status_code: int,
    code: str,
    message: str,
    hint: str | None = None,
) -> None:
    detail: dict[str, str] = {"code": code, "message": message}
    if hint:
        detail["hint"] = hint
    raise HTTPException(status_code=status_code, detail=detail)


class StrategyBundleUpdateRequest(BaseModel):
    expected_revision: str
    mode: Literal["base", "override"]
    yaml: str
    author: str
    reason: str

    @field_validator("expected_revision", "yaml", "author", "reason")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value is required")
        return trimmed


class KpiUpsertRequest(BaseModel):
    expected_revision: str
    dataset_id: str = DEFAULT_DATASET_ID
    kpi: KPIRegistryEntry
    author: str
    reason: str

    @field_validator("expected_revision", "dataset_id", "author", "reason")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value is required")
        return trimmed


class KpiDeleteRequest(BaseModel):
    expected_revision: str
    dataset_id: str = DEFAULT_DATASET_ID
    author: str
    reason: str

    @field_validator("expected_revision", "dataset_id", "author", "reason")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value is required")
        return trimmed


class StrategyOverviewUpdateRequest(BaseModel):
    expected_revision: str
    strategy_context: StrategicContext
    pillars: list[StrategyPillar]
    swot: SWOTBlock | None = None
    author: str
    reason: str

    @field_validator("expected_revision", "author", "reason")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value is required")
        return trimmed


class StrategyTargetPayload(BaseModel):
    kpi_id: str
    target_value: float
    red_threshold: float | None = None
    yellow_threshold: float | None = None
    direction: Literal["up", "down"] = "up"
    owner: str | None = None
    horizon: str | None = None

    @field_validator("kpi_id")
    @classmethod
    def validate_kpi_id(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("kpi_id is required")
        return trimmed


class StrategyTargetUpsertRequest(BaseModel):
    expected_revision: str
    target: StrategyTargetPayload
    author: str
    reason: str

    @field_validator("expected_revision", "author", "reason")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value is required")
        return trimmed


class StrategyTargetDeleteRequest(BaseModel):
    expected_revision: str
    author: str
    reason: str

    @field_validator("expected_revision", "author", "reason")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value is required")
        return trimmed


class StrategyRulePayload(BaseModel):
    id: str
    condition: str
    action: str
    severity: Literal["info", "warn", "block"]
    rationale: str | None = None

    @field_validator("id", "condition", "action")
    @classmethod
    def validate_required(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value is required")
        return trimmed


class StrategyRuleUpsertRequest(BaseModel):
    expected_revision: str
    rule: StrategyRulePayload
    author: str
    reason: str

    @field_validator("expected_revision", "author", "reason")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value is required")
        return trimmed


class StrategyRuleDeleteRequest(BaseModel):
    expected_revision: str
    author: str
    reason: str

    @field_validator("expected_revision", "author", "reason")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value is required")
        return trimmed


def _safe_yaml_text(payload: dict[str, Any]) -> str:
    rendered = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
    return rendered if rendered.endswith("\n") else rendered + "\n"


def _base_kpi_registry_payload() -> dict[str, Any]:
    payload = strategy_storage.load_yaml(strategy_storage.BASE_KPI_PATH)
    if not payload:
        payload = {"schema_version": 1, "version": "1.0.0", "kpis": [], "aliases": {}, "derived_metrics": {}}
    if "kpis" not in payload or not isinstance(payload["kpis"], list):
        payload["kpis"] = []
    if "aliases" not in payload or not isinstance(payload["aliases"], dict):
        payload["aliases"] = {}
    if "derived_metrics" not in payload or not isinstance(payload["derived_metrics"], dict):
        payload["derived_metrics"] = {}
    validated = KPIRegistry.model_validate(payload)
    return validated.model_dump(mode="python")


def _base_strategy_bundle_payload() -> dict[str, Any]:
    payload = strategy_storage.load_yaml(strategy_storage.BASE_STRATEGY_PATH)
    if not payload:
        payload = {
            "schema_version": 1,
            "version": "1.0.0",
            "strategic_context": {
                "company": "Demo Company",
                "horizon": "12 months",
                "north_star_metric": "net_sales_after_returns",
                "narrative": "Baseline strategy bundle.",
            },
            "pillars": [],
            "swot": {
                "strengths": [],
                "weaknesses": [],
                "opportunities": [],
                "threats": [],
            },
            "targets": {},
            "decision_rules": [],
            "scoring_model": {
                "weights": {
                    "kpi_coverage": 0.4,
                    "rule_readiness": 0.2,
                    "hierarchy_readiness": 0.2,
                    "data_readiness": 0.2,
                }
            },
        }
    validated = StrategyBundle.model_validate(payload)
    return validated.model_dump(mode="python")


def _kpi_library_response(*, dataset_id: str, revision: str, kpi_registry_payload: dict[str, Any]) -> dict[str, Any]:
    schema_snapshot = load_dataset_schema(dataset_id)
    return {
        "revision": revision,
        "kpis": kpi_registry_payload.get("kpis", []),
        "available_marts": sorted(schema_snapshot.available_marts),
        "mart_columns": {
            mart_id: sorted(columns)
            for mart_id, columns in sorted(schema_snapshot.mart_columns.items(), key=lambda item: item[0])
        },
    }


def _overview_response(*, revision: str, strategy_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "revision": revision,
        "strategy_context": strategy_payload.get("strategic_context", {}),
        "pillars": strategy_payload.get("pillars", []),
        "swot": strategy_payload.get("swot"),
    }


def _target_entry_payload(kpi_id: str, target_payload: dict[str, Any]) -> dict[str, Any]:
    validated = TargetThreshold.model_validate(target_payload).model_dump(mode="python", exclude_none=True)
    return {
        "kpi_id": kpi_id,
        "target_value": validated.get("target"),
        "red_threshold": validated.get("red_threshold"),
        "yellow_threshold": validated.get("yellow_threshold"),
        "direction": validated.get("direction", "up"),
        "owner": validated.get("owner"),
        "horizon": validated.get("horizon"),
    }


def _kpi_ids_from_registry(kpi_registry_payload: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for item in kpi_registry_payload.get("kpis", []):
        if isinstance(item, dict):
            kpi_id = str(item.get("id", "")).strip()
            if kpi_id:
                ids.append(kpi_id)
    return sorted(set(ids))


def _targets_response(
    *,
    revision: str,
    strategy_payload: dict[str, Any],
    kpi_registry_payload: dict[str, Any],
) -> dict[str, Any]:
    raw_targets = strategy_payload.get("targets", {})
    targets: list[dict[str, Any]] = []
    if isinstance(raw_targets, dict):
        for kpi_id, target_payload in sorted(raw_targets.items(), key=lambda item: str(item[0])):
            if isinstance(target_payload, dict):
                targets.append(_target_entry_payload(str(kpi_id), target_payload))

    return {
        "revision": revision,
        "targets": targets,
        "available_kpis": _kpi_ids_from_registry(kpi_registry_payload),
    }


def _target_threshold_from_payload(payload: StrategyTargetPayload) -> dict[str, Any]:
    validated = TargetThreshold(
        target=payload.target_value,
        red_threshold=payload.red_threshold,
        yellow_threshold=payload.yellow_threshold,
        direction=payload.direction,
        owner=payload.owner,
        horizon=payload.horizon,
    )
    return validated.model_dump(mode="python", exclude_none=True)


_RULE_REFERENCE_RE = re.compile(r"""(?:kpi|target)\(\s*["']([^"']+)["']\s*\)""")


def _extract_rule_kpi_references(condition: str) -> set[str]:
    return {item.strip() for item in _RULE_REFERENCE_RE.findall(condition) if item.strip()}


def _validate_rule_references(condition: str, known_kpis: set[str]) -> list[str]:
    references = _extract_rule_kpi_references(condition)
    return sorted([item for item in references if item not in known_kpis])


def _rules_response(
    *,
    revision: str,
    strategy_payload: dict[str, Any],
    kpi_registry_payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "revision": revision,
        "rules": strategy_payload.get("decision_rules", []),
        "available_kpis": _kpi_ids_from_registry(kpi_registry_payload),
    }


@router.get("/summary")
def get_dataset_strategy_summary(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    store = get_strategy_store()
    _require_bundle(dataset_id)
    return {
        "dataset_id": dataset_id,
        "strategy_hash": store.strategy_hash(dataset_id),
        "digest": store.get_digest(dataset_id),
    }


@router.get("/context")
def get_dataset_strategy_context(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    bundle = _require_bundle(dataset_id)
    return bundle.context.model_dump(mode="json")


@router.get("/targets")
def get_dataset_strategy_targets(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    bundle = _require_bundle(dataset_id)
    return bundle.targets.model_dump(mode="json")


@router.get("/kpis")
def get_dataset_strategy_kpis(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    bundle = _require_bundle(dataset_id)
    return bundle.kpis.model_dump(mode="json")


@router.get("/rules")
def get_dataset_strategy_rules(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    bundle = _require_bundle(dataset_id)
    return bundle.rules.model_dump(mode="json")


@router.get("/scoring")
def get_dataset_strategy_scoring(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    bundle = _require_bundle(dataset_id)
    return bundle.scoring.model_dump(mode="json")


@bundle_router.get("/bundle")
def get_strategy_bundle(
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        merged_strategy, _, revision = load_current_artifacts()
        base_yaml, override_yaml = get_strategy_yaml_texts()
    except StrategyValidationError as exc:
        _raise_error(
            status_code=500,
            code="VALIDATION_ERROR",
            message="Strategy bundle load failed.",
            hint=str(exc),
        )

    return {
        "revision": revision,
        "mode": "merged",
        "bundle": merged_strategy,
        "base_yaml": base_yaml,
        "override_yaml": override_yaml,
    }


@bundle_router.put("/bundle")
def put_strategy_bundle(
    request: StrategyBundleUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        merged_bundle, new_revision = update_strategy_bundle(
            mode=request.mode,
            raw_yaml=request.yaml,
            expected_revision=request.expected_revision,
            author=request.author,
            reason=request.reason,
        )
        base_yaml, override_yaml = get_strategy_yaml_texts()
    except StrategyRevisionConflictError:
        _raise_error(
            status_code=409,
            code="REVISION_CONFLICT",
            message="Revision conflict while saving strategy bundle.",
            hint="Refresh decision state",
        )
    except StrategyYamlParseError as exc:
        _raise_error(
            status_code=422,
            code="YAML_PARSE_ERROR",
            message="Unable to parse strategy YAML.",
            hint=str(exc),
        )
    except StrategyValidationError as exc:
        _raise_error(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Strategy bundle validation failed.",
            hint=str(exc),
        )

    return {
        "revision": new_revision,
        "mode": "merged",
        "bundle": merged_bundle,
        "base_yaml": base_yaml,
        "override_yaml": override_yaml,
    }


@bundle_router.get("/overview")
def get_strategy_overview(
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        base_payload = _base_strategy_bundle_payload()
        revision = get_current_revision_id()
        return _overview_response(revision=revision, strategy_payload=base_payload)
    except StrategyValidationError as exc:
        _raise_error(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Strategy bundle validation failed.",
            hint=str(exc),
        )


@bundle_router.put("/overview")
def put_strategy_overview(
    request: StrategyOverviewUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        base_payload = _base_strategy_bundle_payload()
        base_payload["strategic_context"] = request.strategy_context.model_dump(mode="python", exclude_none=True)
        base_payload["pillars"] = [item.model_dump(mode="python", exclude_none=True) for item in request.pillars]
        base_payload["swot"] = request.swot.model_dump(mode="python", exclude_none=True) if request.swot else None

        _, new_revision = update_strategy_bundle(
            mode="base",
            raw_yaml=_safe_yaml_text(base_payload),
            expected_revision=request.expected_revision,
            author=request.author,
            reason=request.reason,
        )
        refreshed_base = _base_strategy_bundle_payload()
        return _overview_response(revision=new_revision, strategy_payload=refreshed_base)
    except StrategyRevisionConflictError:
        _raise_error(
            status_code=409,
            code="REVISION_CONFLICT",
            message="Revision conflict while updating strategy overview.",
            hint="Refresh decision state",
        )
    except StrategyYamlParseError as exc:
        _raise_error(
            status_code=422,
            code="YAML_PARSE_ERROR",
            message="Unable to parse strategy YAML.",
            hint=str(exc),
        )
    except StrategyValidationError as exc:
        _raise_error(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Strategy bundle validation failed.",
            hint=str(exc),
        )


@bundle_router.get("/targets")
def get_strategy_targets(
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        base_strategy = _base_strategy_bundle_payload()
        base_registry = _base_kpi_registry_payload()
        revision = get_current_revision_id()
        return _targets_response(
            revision=revision,
            strategy_payload=base_strategy,
            kpi_registry_payload=base_registry,
        )
    except StrategyValidationError as exc:
        _raise_error(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Strategy targets validation failed.",
            hint=str(exc),
        )


@bundle_router.post("/targets")
def create_strategy_target(
    request: StrategyTargetUpsertRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        if request.expected_revision != get_current_revision_id():
            raise StrategyRevisionConflictError("stale revision")

        base_strategy = _base_strategy_bundle_payload()
        base_registry = _base_kpi_registry_payload()
        kpi_ids = set(_kpi_ids_from_registry(base_registry))
        if request.target.kpi_id not in kpi_ids:
            _raise_error(
                status_code=422,
                code="VALIDATION_ERROR",
                message=f"KPI '{request.target.kpi_id}' does not exist in KPI registry.",
            )

        targets = base_strategy.get("targets", {})
        if not isinstance(targets, dict):
            targets = {}
        if request.target.kpi_id in targets:
            _raise_error(
                status_code=422,
                code="VALIDATION_ERROR",
                message=f"Target for KPI '{request.target.kpi_id}' already exists.",
            )

        targets[request.target.kpi_id] = _target_threshold_from_payload(request.target)
        base_strategy["targets"] = targets
        _, new_revision = update_strategy_bundle(
            mode="base",
            raw_yaml=_safe_yaml_text(base_strategy),
            expected_revision=request.expected_revision,
            author=request.author,
            reason=request.reason,
        )

        refreshed_strategy = _base_strategy_bundle_payload()
        refreshed_registry = _base_kpi_registry_payload()
        return _targets_response(
            revision=new_revision,
            strategy_payload=refreshed_strategy,
            kpi_registry_payload=refreshed_registry,
        )
    except StrategyRevisionConflictError:
        _raise_error(
            status_code=409,
            code="REVISION_CONFLICT",
            message="Revision conflict while creating target.",
            hint="Refresh decision state",
        )
    except StrategyValidationError as exc:
        _raise_error(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Strategy targets validation failed.",
            hint=str(exc),
        )


@bundle_router.put("/targets/{kpi_id}")
def update_strategy_target(
    kpi_id: str,
    request: StrategyTargetUpsertRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        if request.target.kpi_id != kpi_id:
            _raise_error(
                status_code=422,
                code="VALIDATION_ERROR",
                message="KPI id in path and body must match.",
            )

        if request.expected_revision != get_current_revision_id():
            raise StrategyRevisionConflictError("stale revision")

        base_strategy = _base_strategy_bundle_payload()
        base_registry = _base_kpi_registry_payload()
        kpi_ids = set(_kpi_ids_from_registry(base_registry))
        if request.target.kpi_id not in kpi_ids:
            _raise_error(
                status_code=422,
                code="VALIDATION_ERROR",
                message=f"KPI '{request.target.kpi_id}' does not exist in KPI registry.",
            )

        targets = base_strategy.get("targets", {})
        if not isinstance(targets, dict):
            targets = {}
        if kpi_id not in targets:
            _raise_error(status_code=404, code="NOT_FOUND", message=f"Target '{kpi_id}' not found.")

        targets[kpi_id] = _target_threshold_from_payload(request.target)
        base_strategy["targets"] = targets
        _, new_revision = update_strategy_bundle(
            mode="base",
            raw_yaml=_safe_yaml_text(base_strategy),
            expected_revision=request.expected_revision,
            author=request.author,
            reason=request.reason,
        )

        refreshed_strategy = _base_strategy_bundle_payload()
        refreshed_registry = _base_kpi_registry_payload()
        return _targets_response(
            revision=new_revision,
            strategy_payload=refreshed_strategy,
            kpi_registry_payload=refreshed_registry,
        )
    except StrategyRevisionConflictError:
        _raise_error(
            status_code=409,
            code="REVISION_CONFLICT",
            message="Revision conflict while updating target.",
            hint="Refresh decision state",
        )
    except StrategyValidationError as exc:
        _raise_error(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Strategy targets validation failed.",
            hint=str(exc),
        )


@bundle_router.delete("/targets/{kpi_id}")
def delete_strategy_target(
    kpi_id: str,
    request: StrategyTargetDeleteRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        if request.expected_revision != get_current_revision_id():
            raise StrategyRevisionConflictError("stale revision")

        base_strategy = _base_strategy_bundle_payload()
        targets = base_strategy.get("targets", {})
        if not isinstance(targets, dict):
            targets = {}
        if kpi_id not in targets:
            _raise_error(status_code=404, code="NOT_FOUND", message=f"Target '{kpi_id}' not found.")

        targets.pop(kpi_id, None)
        base_strategy["targets"] = targets
        _, new_revision = update_strategy_bundle(
            mode="base",
            raw_yaml=_safe_yaml_text(base_strategy),
            expected_revision=request.expected_revision,
            author=request.author,
            reason=request.reason,
        )

        refreshed_strategy = _base_strategy_bundle_payload()
        refreshed_registry = _base_kpi_registry_payload()
        return _targets_response(
            revision=new_revision,
            strategy_payload=refreshed_strategy,
            kpi_registry_payload=refreshed_registry,
        )
    except StrategyRevisionConflictError:
        _raise_error(
            status_code=409,
            code="REVISION_CONFLICT",
            message="Revision conflict while deleting target.",
            hint="Refresh decision state",
        )
    except StrategyValidationError as exc:
        _raise_error(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Strategy targets validation failed.",
            hint=str(exc),
        )


@bundle_router.get("/rules")
def get_strategy_rules(
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        base_strategy = _base_strategy_bundle_payload()
        base_registry = _base_kpi_registry_payload()
        revision = get_current_revision_id()
        return _rules_response(
            revision=revision,
            strategy_payload=base_strategy,
            kpi_registry_payload=base_registry,
        )
    except StrategyValidationError as exc:
        _raise_error(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Strategy rules validation failed.",
            hint=str(exc),
        )


@bundle_router.post("/rules")
def create_strategy_rule(
    request: StrategyRuleUpsertRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        if request.expected_revision != get_current_revision_id():
            raise StrategyRevisionConflictError("stale revision")

        base_strategy = _base_strategy_bundle_payload()
        base_registry = _base_kpi_registry_payload()
        known_kpis = set(_kpi_ids_from_registry(base_registry))
        missing_refs = _validate_rule_references(request.rule.condition, known_kpis)
        if missing_refs:
            _raise_error(
                status_code=422,
                code="VALIDATION_ERROR",
                message=f"Rule references unknown KPI ids: {', '.join(missing_refs)}",
            )

        rules = base_strategy.get("decision_rules", [])
        if not isinstance(rules, list):
            rules = []
        if any(isinstance(item, dict) and item.get("id") == request.rule.id for item in rules):
            _raise_error(
                status_code=422,
                code="VALIDATION_ERROR",
                message=f"Rule '{request.rule.id}' already exists.",
            )

        rules.append(request.rule.model_dump(mode="python", exclude_none=True))
        base_strategy["decision_rules"] = rules
        _, new_revision = update_strategy_bundle(
            mode="base",
            raw_yaml=_safe_yaml_text(base_strategy),
            expected_revision=request.expected_revision,
            author=request.author,
            reason=request.reason,
        )

        refreshed_strategy = _base_strategy_bundle_payload()
        refreshed_registry = _base_kpi_registry_payload()
        return _rules_response(
            revision=new_revision,
            strategy_payload=refreshed_strategy,
            kpi_registry_payload=refreshed_registry,
        )
    except StrategyRevisionConflictError:
        _raise_error(
            status_code=409,
            code="REVISION_CONFLICT",
            message="Revision conflict while creating rule.",
            hint="Refresh decision state",
        )
    except StrategyValidationError as exc:
        _raise_error(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Strategy rules validation failed.",
            hint=str(exc),
        )


@bundle_router.put("/rules/{rule_id}")
def update_strategy_rule(
    rule_id: str,
    request: StrategyRuleUpsertRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        if request.rule.id != rule_id:
            _raise_error(
                status_code=422,
                code="VALIDATION_ERROR",
                message="Rule id in path and body must match.",
            )
        if request.expected_revision != get_current_revision_id():
            raise StrategyRevisionConflictError("stale revision")

        base_strategy = _base_strategy_bundle_payload()
        base_registry = _base_kpi_registry_payload()
        known_kpis = set(_kpi_ids_from_registry(base_registry))
        missing_refs = _validate_rule_references(request.rule.condition, known_kpis)
        if missing_refs:
            _raise_error(
                status_code=422,
                code="VALIDATION_ERROR",
                message=f"Rule references unknown KPI ids: {', '.join(missing_refs)}",
            )

        rules = base_strategy.get("decision_rules", [])
        if not isinstance(rules, list):
            rules = []
        updated = False
        updated_rules: list[dict[str, Any]] = []
        for item in rules:
            if isinstance(item, dict) and item.get("id") == rule_id:
                updated_rules.append(request.rule.model_dump(mode="python", exclude_none=True))
                updated = True
            elif isinstance(item, dict):
                updated_rules.append(item)
        if not updated:
            _raise_error(status_code=404, code="NOT_FOUND", message=f"Rule '{rule_id}' not found.")

        base_strategy["decision_rules"] = updated_rules
        _, new_revision = update_strategy_bundle(
            mode="base",
            raw_yaml=_safe_yaml_text(base_strategy),
            expected_revision=request.expected_revision,
            author=request.author,
            reason=request.reason,
        )

        refreshed_strategy = _base_strategy_bundle_payload()
        refreshed_registry = _base_kpi_registry_payload()
        return _rules_response(
            revision=new_revision,
            strategy_payload=refreshed_strategy,
            kpi_registry_payload=refreshed_registry,
        )
    except StrategyRevisionConflictError:
        _raise_error(
            status_code=409,
            code="REVISION_CONFLICT",
            message="Revision conflict while updating rule.",
            hint="Refresh decision state",
        )
    except StrategyValidationError as exc:
        _raise_error(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Strategy rules validation failed.",
            hint=str(exc),
        )


@bundle_router.delete("/rules/{rule_id}")
def delete_strategy_rule(
    rule_id: str,
    request: StrategyRuleDeleteRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        if request.expected_revision != get_current_revision_id():
            raise StrategyRevisionConflictError("stale revision")

        base_strategy = _base_strategy_bundle_payload()
        rules = base_strategy.get("decision_rules", [])
        if not isinstance(rules, list):
            rules = []
        next_rules = [item for item in rules if not (isinstance(item, dict) and item.get("id") == rule_id)]
        if len(next_rules) == len(rules):
            _raise_error(status_code=404, code="NOT_FOUND", message=f"Rule '{rule_id}' not found.")

        base_strategy["decision_rules"] = next_rules
        _, new_revision = update_strategy_bundle(
            mode="base",
            raw_yaml=_safe_yaml_text(base_strategy),
            expected_revision=request.expected_revision,
            author=request.author,
            reason=request.reason,
        )

        refreshed_strategy = _base_strategy_bundle_payload()
        refreshed_registry = _base_kpi_registry_payload()
        return _rules_response(
            revision=new_revision,
            strategy_payload=refreshed_strategy,
            kpi_registry_payload=refreshed_registry,
        )
    except StrategyRevisionConflictError:
        _raise_error(
            status_code=409,
            code="REVISION_CONFLICT",
            message="Revision conflict while deleting rule.",
            hint="Refresh decision state",
        )
    except StrategyValidationError as exc:
        _raise_error(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Strategy rules validation failed.",
            hint=str(exc),
        )


@bundle_router.get("/kpis")
def get_strategy_kpis(
    dataset_id: str = DEFAULT_DATASET_ID,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        base_registry = _base_kpi_registry_payload()
        revision = get_current_revision_id()
        return _kpi_library_response(dataset_id=dataset_id, revision=revision, kpi_registry_payload=base_registry)
    except KeyError as exc:
        _raise_error(status_code=404, code="NOT_FOUND", message=str(exc))
    except StrategyValidationError as exc:
        _raise_error(status_code=422, code="VALIDATION_ERROR", message="KPI registry validation failed.", hint=str(exc))


@bundle_router.post("/kpis")
def create_strategy_kpi(
    request: KpiUpsertRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        if request.expected_revision != get_current_revision_id():
            raise StrategyRevisionConflictError("stale revision")

        base_registry = _base_kpi_registry_payload()
        kpis = list(base_registry.get("kpis", []))
        if any(item.get("id") == request.kpi.id for item in kpis if isinstance(item, dict)):
            _raise_error(
                status_code=422,
                code="VALIDATION_ERROR",
                message=f"KPI '{request.kpi.id}' already exists.",
            )

        kpis.append(request.kpi.model_dump(mode="python", exclude_none=True))
        base_registry["kpis"] = kpis

        _, new_revision = update_kpi_registry(
            mode="base",
            raw_yaml=_safe_yaml_text(base_registry),
            expected_revision=request.expected_revision,
            author=request.author,
            reason=request.reason,
        )

        refreshed_base = _base_kpi_registry_payload()
        return _kpi_library_response(dataset_id=request.dataset_id, revision=new_revision, kpi_registry_payload=refreshed_base)
    except StrategyRevisionConflictError:
        _raise_error(
            status_code=409,
            code="REVISION_CONFLICT",
            message="Revision conflict while creating KPI.",
            hint="Refresh decision state",
        )
    except StrategyYamlParseError as exc:
        _raise_error(status_code=422, code="YAML_PARSE_ERROR", message="Unable to parse KPI registry YAML.", hint=str(exc))
    except StrategyValidationError as exc:
        _raise_error(status_code=422, code="VALIDATION_ERROR", message="KPI registry validation failed.", hint=str(exc))
    except KeyError as exc:
        _raise_error(status_code=404, code="NOT_FOUND", message=str(exc))


@bundle_router.put("/kpis/{kpi_id}")
def update_strategy_kpi(
    kpi_id: str,
    request: KpiUpsertRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        if request.kpi.id != kpi_id:
            _raise_error(
                status_code=422,
                code="VALIDATION_ERROR",
                message="KPI id in path and body must match.",
            )

        if request.expected_revision != get_current_revision_id():
            raise StrategyRevisionConflictError("stale revision")

        base_registry = _base_kpi_registry_payload()
        kpis = list(base_registry.get("kpis", []))

        updated = False
        next_items: list[dict[str, Any]] = []
        for item in kpis:
            if isinstance(item, dict) and item.get("id") == kpi_id:
                next_items.append(request.kpi.model_dump(mode="python", exclude_none=True))
                updated = True
            elif isinstance(item, dict):
                next_items.append(item)

        if not updated:
            _raise_error(status_code=404, code="NOT_FOUND", message=f"KPI '{kpi_id}' not found.")

        base_registry["kpis"] = next_items
        _, new_revision = update_kpi_registry(
            mode="base",
            raw_yaml=_safe_yaml_text(base_registry),
            expected_revision=request.expected_revision,
            author=request.author,
            reason=request.reason,
        )
        refreshed_base = _base_kpi_registry_payload()
        return _kpi_library_response(dataset_id=request.dataset_id, revision=new_revision, kpi_registry_payload=refreshed_base)
    except StrategyRevisionConflictError:
        _raise_error(
            status_code=409,
            code="REVISION_CONFLICT",
            message="Revision conflict while updating KPI.",
            hint="Refresh decision state",
        )
    except StrategyYamlParseError as exc:
        _raise_error(status_code=422, code="YAML_PARSE_ERROR", message="Unable to parse KPI registry YAML.", hint=str(exc))
    except StrategyValidationError as exc:
        _raise_error(status_code=422, code="VALIDATION_ERROR", message="KPI registry validation failed.", hint=str(exc))
    except KeyError as exc:
        _raise_error(status_code=404, code="NOT_FOUND", message=str(exc))


@bundle_router.delete("/kpis/{kpi_id}")
def delete_strategy_kpi(
    kpi_id: str,
    request: KpiDeleteRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        if request.expected_revision != get_current_revision_id():
            raise StrategyRevisionConflictError("stale revision")

        base_registry = _base_kpi_registry_payload()
        kpis = list(base_registry.get("kpis", []))
        next_items = [item for item in kpis if not (isinstance(item, dict) and item.get("id") == kpi_id)]
        if len(next_items) == len(kpis):
            _raise_error(status_code=404, code="NOT_FOUND", message=f"KPI '{kpi_id}' not found.")

        base_registry["kpis"] = next_items
        _, new_revision = update_kpi_registry(
            mode="base",
            raw_yaml=_safe_yaml_text(base_registry),
            expected_revision=request.expected_revision,
            author=request.author,
            reason=request.reason,
        )
        refreshed_base = _base_kpi_registry_payload()
        return _kpi_library_response(dataset_id=request.dataset_id, revision=new_revision, kpi_registry_payload=refreshed_base)
    except StrategyRevisionConflictError:
        _raise_error(
            status_code=409,
            code="REVISION_CONFLICT",
            message="Revision conflict while deleting KPI.",
            hint="Refresh decision state",
        )
    except StrategyYamlParseError as exc:
        _raise_error(status_code=422, code="YAML_PARSE_ERROR", message="Unable to parse KPI registry YAML.", hint=str(exc))
    except StrategyValidationError as exc:
        _raise_error(status_code=422, code="VALIDATION_ERROR", message="KPI registry validation failed.", hint=str(exc))
    except KeyError as exc:
        _raise_error(status_code=404, code="NOT_FOUND", message=str(exc))
