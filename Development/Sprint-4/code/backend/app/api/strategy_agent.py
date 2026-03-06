"""StrategyAgent API routes for extraction/reconciliation/apply scaffolding."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.mart_registry import DEFAULT_DATASET_ID
from app.core.security import get_current_user
from app.db.models import User
from app.services.strategy.agent import (
    apply_patch,
    apply_selected_patches,
    cache_reconcile_patches,
    extract_kpis_from_text,
    reconcile_kpis,
    undo_patch,
)
from app.services.strategy.errors import StrategyRevisionConflictError, StrategyValidationError
from app.services.strategy.schema_provider import load_dataset_schema
from app.services.strategy.storage import get_current_revision_id

router = APIRouter(prefix="/strategy/agent", tags=["strategy"])


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


class ExtractKpisRequest(BaseModel):
    dataset_id: str = DEFAULT_DATASET_ID
    text: str
    expected_revision: str | None = None

    @field_validator("dataset_id", "text")
    @classmethod
    def validate_required(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value is required")
        return trimmed


class ReconcileKpisRequest(BaseModel):
    dataset_id: str = DEFAULT_DATASET_ID
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    expected_revision: str | None = None

    @field_validator("dataset_id")
    @classmethod
    def validate_dataset_id(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value is required")
        return trimmed


class ApplyPatchRequest(BaseModel):
    dataset_id: str = DEFAULT_DATASET_ID
    selected_patch_ids: list[str] = Field(default_factory=list)
    patches: list[dict[str, Any]] | None = None
    patch: dict[str, Any] | None = None
    expected_revision: str
    author: str
    reason: str

    @field_validator("dataset_id", "expected_revision", "author", "reason")
    @classmethod
    def validate_required(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value is required")
        return trimmed


class UndoPatchRequest(BaseModel):
    dataset_id: str = DEFAULT_DATASET_ID
    revision_to_restore: str
    expected_revision: str | None = None
    author: str
    reason: str

    @field_validator("dataset_id", "revision_to_restore", "author", "reason")
    @classmethod
    def validate_required(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value is required")
        return trimmed


def _enforce_expected_revision(expected_revision: str | None) -> None:
    if not expected_revision:
        return
    if expected_revision != get_current_revision_id():
        _raise_error(
            status_code=409,
            code="REVISION_CONFLICT",
            message="Revision conflict while processing strategy agent request.",
            hint="Refresh decision state",
        )


@router.post("/extract-kpis")
def extract_strategy_kpis(
    request: ExtractKpisRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    _enforce_expected_revision(request.expected_revision)
    try:
        result = extract_kpis_from_text(request.text, request.dataset_id)
    except KeyError as exc:
        _raise_error(status_code=404, code="NOT_FOUND", message=str(exc))
    except StrategyValidationError as exc:
        _raise_error(status_code=422, code="VALIDATION_ERROR", message=str(exc))

    return {
        "revision": get_current_revision_id(),
        "candidates": result.get("candidates", []),
        "notes": result.get("notes", []),
        "suggested_patches": result.get("suggested_patches", []),
    }


@router.post("/reconcile")
def reconcile_strategy_kpis(
    request: ReconcileKpisRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    _enforce_expected_revision(request.expected_revision)
    try:
        snapshot = load_dataset_schema(request.dataset_id)
        result = reconcile_kpis(request.candidates, snapshot)
        revision = get_current_revision_id()
        cache_reconcile_patches(request.dataset_id, revision, result.get("patches", []))
    except KeyError as exc:
        _raise_error(status_code=404, code="NOT_FOUND", message=str(exc))
    except StrategyValidationError as exc:
        _raise_error(status_code=422, code="VALIDATION_ERROR", message=str(exc))

    return {
        "revision": revision,
        "candidates": result.get("candidates", []),
        "reconciled": result.get("reconciled", []),
        "missing": result.get("missing", []),
        "missing_dependencies": result.get("missing_dependencies", []),
        "suggestions": result.get("suggestions", []),
        "column_matches": result.get("column_matches", []),
        "patches": result.get("patches", []),
    }


@router.post("/apply")
def apply_strategy_patch(
    request: ApplyPatchRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        if request.selected_patch_ids:
            result = apply_selected_patches(
                dataset_id=request.dataset_id,
                selected_patch_ids=request.selected_patch_ids,
                expected_revision=request.expected_revision,
                author=request.author,
                reason=request.reason,
                explicit_patches=request.patches,
            )
        elif request.patch is not None:
            result = apply_patch(
                dataset_id=request.dataset_id,
                patch=request.patch,
                expected_revision=request.expected_revision,
                author=request.author,
                reason=request.reason,
            )
        elif request.patches:
            patch_ids = [
                str(item.get("patch_id"))
                for item in request.patches
                if isinstance(item, dict) and str(item.get("patch_id") or "").strip()
            ]
            result = apply_selected_patches(
                dataset_id=request.dataset_id,
                selected_patch_ids=patch_ids,
                expected_revision=request.expected_revision,
                author=request.author,
                reason=request.reason,
                explicit_patches=request.patches,
            )
        else:
            _raise_error(
                status_code=422,
                code="VALIDATION_ERROR",
                message="No patch input provided. Send selected_patch_ids, patches, or patch.",
            )
    except StrategyRevisionConflictError:
        _raise_error(
            status_code=409,
            code="REVISION_CONFLICT",
            message="Revision conflict while applying strategy patch.",
            hint="Refresh decision state",
        )
    except KeyError as exc:
        _raise_error(status_code=404, code="NOT_FOUND", message=str(exc))
    except StrategyValidationError as exc:
        _raise_error(status_code=422, code="VALIDATION_ERROR", message=str(exc))

    return result


@router.post("/undo")
def undo_strategy_patch(
    request: UndoPatchRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    expected_revision = request.expected_revision or get_current_revision_id()
    try:
        result = undo_patch(
            revision_to_restore=request.revision_to_restore,
            expected_revision=expected_revision,
            author=request.author,
            reason=request.reason,
        )
    except StrategyRevisionConflictError:
        _raise_error(
            status_code=409,
            code="REVISION_CONFLICT",
            message="Revision conflict while restoring revision snapshot.",
            hint="Refresh decision state",
        )
    except StrategyValidationError as exc:
        _raise_error(status_code=422, code="VALIDATION_ERROR", message=str(exc))

    return result
