"""Dataset-scoped strategy API routes."""

from __future__ import annotations

from typing import Any
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
import yaml

from app.core.mart_registry import DEFAULT_DATASET_ID
from app.core.security import get_current_user
from app.db.models import User
from app.models.kpi_registry import KPIRegistry, KPIRegistryEntry
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
