"""Dataset-scoped chat API."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.services.agents.chat_models import ChatRequest, ChatResponseUnion
from app.services.agents.chat_orchestrator import response_chart_spec_hash, run_chat_orchestration

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ChatResponseUnion)
def chat_with_dataset(
    dataset_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    started_at = time.perf_counter()

    if not request.table:
        raise HTTPException(status_code=400, detail="Select a mart first")

    try:
        payload = run_chat_orchestration(
            dataset_id=dataset_id,
            message=request.message,
            table=request.table,
            state=request.state,
            db=db,
        )
    except HTTPException as exc:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.warning(
            "chat_request_failed user_id=%s dataset_id=%s table=%s status=%s detail=%s duration_ms=%.2f",
            current_user.id,
            dataset_id,
            request.table,
            exc.status_code,
            exc.detail,
            elapsed_ms,
        )
        raise

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response_type = str(payload.get("response_type", "unknown"))
    chart_hash = response_chart_spec_hash(payload) or "-"
    logger.info(
        "chat_request user_id=%s dataset_id=%s table=%s response_type=%s chart_spec_hash=%s duration_ms=%.2f",
        current_user.id,
        dataset_id,
        request.table,
        response_type,
        chart_hash,
        elapsed_ms,
    )
    return payload
