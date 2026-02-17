"""Schemas for legacy chart-data endpoint compatibility."""

from __future__ import annotations

from pydantic import BaseModel


class LegacyChartDataResponse(BaseModel):
    """Legacy chart-data response contract used by existing frontend flows."""

    x: list[str]
    y: list[float]
    title: str
    x_axis_label: str
    y_axis_label: str

