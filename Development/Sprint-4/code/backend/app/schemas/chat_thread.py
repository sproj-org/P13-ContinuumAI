from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime


class ChatThreadUpsert(BaseModel):
    """Schema for creating or updating a chat thread (keyed by thread_key)."""
    thread_key: str = Field(..., max_length=255, description="e.g. silkroute:gold_sales_daily")
    turns: list[dict[str, Any]] = Field(default_factory=list)
    chat_state: Optional[dict[str, Any]] = None
    last_chart_spec: Optional[dict[str, Any]] = None
    saved_prompts: list[str] = Field(default_factory=list)
    chat_mode: str = "auto"


class ChatThreadResponse(BaseModel):
    """Schema for returning a chat thread."""
    id: int
    thread_key: str
    turns: list[dict[str, Any]]
    chat_state: Optional[dict[str, Any]]
    last_chart_spec: Optional[dict[str, Any]]
    saved_prompts: list[str]
    chat_mode: str
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, obj: Any) -> "ChatThreadResponse":
        return cls(
            id=obj.id,
            thread_key=obj.thread_key,
            turns=obj.turns or [],
            chat_state=obj.chat_state,
            last_chart_spec=obj.last_chart_spec,
            saved_prompts=obj.saved_prompts or [],
            chat_mode=obj.chat_mode or "auto",
            updated_at=obj.updated_at,
        )
