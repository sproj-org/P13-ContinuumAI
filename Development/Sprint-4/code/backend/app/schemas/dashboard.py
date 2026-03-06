from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime


class SavedChartCreate(BaseModel):
    """Schema for creating a saved chart."""
    dataset_id: str
    mart_id: str
    title: str = Field(..., max_length=500)
    chart_spec: dict[str, Any]
    rows: list[dict[str, Any]]
    position: int = 0


class SavedChartUpdate(BaseModel):
    """Schema for updating a saved chart."""
    title: Optional[str] = Field(None, max_length=500)
    position: Optional[int] = None


class SavedChartResponse(BaseModel):
    """Schema for returning a saved chart."""
    id: int
    dataset_id: str
    mart_id: str
    title: str
    chart_spec: dict[str, Any]
    rows: list[dict[str, Any]]
    position: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, obj: Any) -> "SavedChartResponse":
        return cls(
            id=obj.id,
            dataset_id=obj.dataset_id,
            mart_id=obj.mart_id,
            title=obj.title,
            chart_spec=obj.chart_spec,
            rows=obj.rows_snapshot,
            position=obj.position,
            created_at=obj.created_at,
        )
