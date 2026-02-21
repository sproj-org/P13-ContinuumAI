"""Dataset-scoped strategy API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.db.models import User
from app.services.strategy.errors import StrategyNotFoundError, StrategyValidationError
from app.services.strategy.store import get_strategy_store

router = APIRouter(prefix="/strategy", tags=["strategy"])


def _require_bundle(dataset_id: str):
    store = get_strategy_store()
    try:
        return store.load_bundle(dataset_id)
    except StrategyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StrategyValidationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
