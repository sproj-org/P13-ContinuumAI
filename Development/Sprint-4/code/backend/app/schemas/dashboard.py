from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime


class SavedChartCreate(BaseModel):
    """Schema for creating a saved chart."""
    dataset_id: str
    dashboard_name: str = Field(default="Default", max_length=120)
    mart_id: str
    title: str = Field(..., max_length=500)
    chart_spec: dict[str, Any]
    rows: list[dict[str, Any]]
    position: int = 0


class SavedChartUpdate(BaseModel):
    """Schema for updating a saved chart."""
    title: Optional[str] = Field(None, max_length=500)
    dashboard_name: Optional[str] = Field(None, max_length=120)
    position: Optional[int] = None


class SavedChartResponse(BaseModel):
    """Schema for returning a saved chart."""
    id: int
    dataset_id: str
    dashboard_name: str
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
            dashboard_name=obj.dashboard_name,
            mart_id=obj.mart_id,
            title=obj.title,
            chart_spec=obj.chart_spec,
            rows=obj.rows_snapshot,
            position=obj.position,
            created_at=obj.created_at,
        )


class UserDashboardCreate(BaseModel):
    dataset_id: str
    name: str = Field(..., max_length=120)


class UserDashboardUpdate(BaseModel):
    name: str = Field(..., max_length=120)


class UserDashboardResponse(BaseModel):
    id: int
    dataset_id: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}
