"""Dataset-scoped strategy API routes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.core.security import get_current_user
from app.db.models import User
from app.services.strategy.errors import (
    StrategyNotFoundError,
    StrategyRevisionConflictError,
    StrategyValidationError,
    StrategyYamlParseError,
)
from app.services.strategy.storage import (
    get_strategy_yaml_texts,
    load_current_artifacts,
    update_strategy_bundle,
)
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
