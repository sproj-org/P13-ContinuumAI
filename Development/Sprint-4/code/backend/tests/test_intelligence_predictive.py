from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_intelligence_predictive.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.services.intelligence.predictive import (  # noqa: E402
    build_strategy_risk_summary,
    detect_series_anomalies,
    summarize_prediction_from_series,
)
from app.services.intelligence.specs import PredictionSpec  # noqa: E402


def test_detect_series_anomalies_flags_large_spike() -> None:
    labels = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06", "2024-07"]
    values = [10.0, 11.0, 12.0, 11.0, 10.0, 42.0, 11.0]

    anomalies = detect_series_anomalies(labels, values, sensitivity=2.0, window=5)

    assert len(anomalies) == 1
    assert anomalies[0].label == "2024-06"
    assert anomalies[0].severity == "high"


def test_summarize_prediction_from_series_adds_forecast_points_and_risk() -> None:
    spec = PredictionSpec(
        mode="risk",
        dataset_id="silkroute",
        table="gold_sales_daily",
        metric="net_sales",
        aggregation="sum",
        time_field="sales_date",
        time_grain="month",
        horizon=3,
        target_value=20.0,
        target_direction="up",
    )

    summary = summarize_prediction_from_series(
        labels=["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"],
        values=[10.0, 12.0, 14.0, 16.0, 18.0],
        spec=spec,
    )

    assert summary.mode == "risk"
    assert len(summary.points) == 8
    assert summary.points[-1].is_forecast is True
    assert summary.projected_change_pct is not None
    assert summary.risk_band == "low"


def test_build_strategy_risk_summary_uses_prediction_terminal_value() -> None:
    spec = PredictionSpec(
        mode="risk",
        dataset_id="silkroute",
        table="gold_sales_daily",
        metric="net_sales",
        aggregation="sum",
        time_field="sales_date",
        time_grain="month",
        horizon=2,
        target_value=25.0,
        target_direction="up",
    )
    prediction = summarize_prediction_from_series(
        labels=["2024-01", "2024-02", "2024-03", "2024-04"],
        values=[10.0, 12.0, 13.0, 14.0],
        spec=spec,
    )

    summary = build_strategy_risk_summary(
        kpi_id="total_sales",
        target_value=25.0,
        current_value=14.0,
        prediction=prediction,
        direction="up",
    )

    assert summary.kpi_id == "total_sales"
    assert summary.projected_value is not None
    assert summary.projected_value > summary.current_value
    assert summary.risk_band in {"medium", "high"}
