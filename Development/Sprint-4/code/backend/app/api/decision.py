"""Task-2 decision state API routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.mart_registry import DEFAULT_DATASET_ID
from app.core.security import get_current_user
from app.db.models import User
from app.models.decision_state import DecisionStatePayload
from app.models.kpi_registry import KPIRegistry
from app.models.strategy_bundle import StrategyBundle
from app.services.strategy.coverage import compute_readiness_and_coverage
from app.services.strategy.schema_provider import load_dataset_schema
from app.services.strategy.storage import load_current_artifacts

router = APIRouter(prefix="/decision", tags=["decision"])


@router.get("/state")
def get_decision_state(
    dataset_id: str = DEFAULT_DATASET_ID,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        strategy_payload, kpi_payload, revision = load_current_artifacts()
        strategy_bundle = StrategyBundle.model_validate(strategy_payload)
        kpi_registry = KPIRegistry.model_validate(kpi_payload)
        schema_snapshot = load_dataset_schema(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"Decision state load failed: {exc}") from exc

    readiness, coverage_gaps, summaries = compute_readiness_and_coverage(
        strategy_bundle=strategy_bundle,
        kpi_registry=kpi_registry,
        schema_snapshot=schema_snapshot,
    )
    payload = DecisionStatePayload(
        revision=revision,
        generated_at=datetime.now(timezone.utc),
        strategy_bundle=strategy_bundle.model_dump(mode="python"),
        kpi_registry=kpi_registry.model_dump(mode="python"),
        readiness=readiness,
        coverage_gaps=coverage_gaps,
        summaries=summaries,
    )
    return payload.model_dump(mode="json")
