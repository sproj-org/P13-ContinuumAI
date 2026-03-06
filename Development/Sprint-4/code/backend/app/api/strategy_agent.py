"""StrategyAgent API routes for extraction/reconciliation/apply scaffolding."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.mart_registry import DEFAULT_DATASET_ID
from app.core.security import get_current_user
from app.db.models import User
from app.services.strategy.agent import apply_patch, extract_kpis_from_text, reconcile_kpis
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
    patch: dict[str, Any]
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
    except KeyError as exc:
        _raise_error(status_code=404, code="NOT_FOUND", message=str(exc))
    except StrategyValidationError as exc:
        _raise_error(status_code=422, code="VALIDATION_ERROR", message=str(exc))

    return {
        "revision": get_current_revision_id(),
        "candidates": result.get("candidates", []),
        "reconciled": result.get("reconciled", []),
        "missing": result.get("missing", []),
        "missing_dependencies": result.get("missing_dependencies", []),
        "suggestions": result.get("suggestions", []),
        "column_matches": result.get("column_matches", []),
    }


@router.post("/apply")
def apply_strategy_patch(
    request: ApplyPatchRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        result = apply_patch(
            dataset_id=request.dataset_id,
            patch=request.patch,
            expected_revision=request.expected_revision,
            author=request.author,
            reason=request.reason,
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
