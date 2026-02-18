"""Dataset-scoped chat API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.services.agents.chat_orchestrator import run_chat_orchestration

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    table: str | None = None
    state: dict[str, Any] | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("message is required")
        return value.strip()


class ChatResponse(BaseModel):
    response_type: str
    chart_spec: dict[str, Any]
    columns: list[str]
    rows: list[dict[str, Any]]
    narrative: str
    meta: dict[str, Any]


@router.post("", response_model=ChatResponse)
def chat_with_dataset(
    dataset_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    if not request.table:
        raise HTTPException(status_code=400, detail="Select a mart first")

    return run_chat_orchestration(
        dataset_id=dataset_id,
        message=request.message,
        table=request.table,
        state=request.state,
        db=db,
    )
