"""Task-2 KPI registry API routes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.core.security import get_current_user
from app.db.models import User
from app.services.strategy.errors import (
    StrategyRevisionConflictError,
    StrategyValidationError,
    StrategyYamlParseError,
)
from app.services.strategy.storage import get_kpi_registry_yaml_texts, load_current_artifacts, update_kpi_registry

router = APIRouter(prefix="/kpi-registry", tags=["kpi-registry"])


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


class KPIRegistryUpdateRequest(BaseModel):
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


@router.get("/bundle")
def get_kpi_registry_bundle(
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        _, merged_kpi, revision = load_current_artifacts()
        base_yaml, override_yaml = get_kpi_registry_yaml_texts()
    except StrategyValidationError as exc:
        _raise_error(
            status_code=500,
            code="VALIDATION_ERROR",
            message="KPI registry load failed.",
            hint=str(exc),
        )

    return {
        "revision": revision,
        "mode": "merged",
        "bundle": merged_kpi,
        "base_yaml": base_yaml,
        "override_yaml": override_yaml,
    }


@router.put("/bundle")
def put_kpi_registry_bundle(
    request: KPIRegistryUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        merged_registry, new_revision = update_kpi_registry(
            mode=request.mode,
            raw_yaml=request.yaml,
            expected_revision=request.expected_revision,
            author=request.author,
            reason=request.reason,
        )
        base_yaml, override_yaml = get_kpi_registry_yaml_texts()
    except StrategyRevisionConflictError:
        _raise_error(
            status_code=409,
            code="REVISION_CONFLICT",
            message="Revision conflict while saving KPI registry.",
            hint="Refresh decision state",
        )
    except StrategyYamlParseError as exc:
        _raise_error(
            status_code=422,
            code="YAML_PARSE_ERROR",
            message="Unable to parse KPI registry YAML.",
            hint=str(exc),
        )
    except StrategyValidationError as exc:
        _raise_error(
            status_code=422,
            code="VALIDATION_ERROR",
            message="KPI registry validation failed.",
            hint=str(exc),
        )

    return {
        "revision": new_revision,
        "mode": "merged",
        "bundle": merged_registry,
        "base_yaml": base_yaml,
        "override_yaml": override_yaml,
    }
