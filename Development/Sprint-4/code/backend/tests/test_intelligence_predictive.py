from __future__ import annotations

import os
from types import SimpleNamespace

import pandas as pd
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_intelligence_predictive.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from fastapi import HTTPException  # noqa: E402
from app.services.intelligence.formula_engine import build_formula_time_series  # noqa: E402
from app.services.intelligence.predictive import (  # noqa: E402
    build_strategy_risk_summary,
    detect_series_anomalies,
    run_prediction_analysis,
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
    assert summary.observed_points == 5
    assert summary.display_label == "net_sales"


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
        kpi_label="Total Sales",
        target_value=25.0,
        current_value=14.0,
        prediction=prediction,
        direction="up",
        target_horizon="FY26",
        recommended_actions=["Inspect weak regions"],
        supporting_details=["4 observed periods"],
    )

    assert summary.kpi_id == "total_sales"
    assert summary.kpi_label == "Total Sales"
    assert summary.projected_value is not None
    assert summary.projected_value > summary.current_value
    assert summary.risk_band in {"medium", "high"}
    assert summary.target_horizon == "FY26"
    assert summary.recommended_actions == ["Inspect weak regions"]


def test_build_formula_time_series_handles_duplicate_metric_columns_for_ratio() -> None:
    frame = pd.DataFrame(
        [
            ["2024-01-01", 2.0, 2.0],
            ["2024-01-02", 4.0, 4.0],
            ["2024-02-01", None, None],
        ],
        columns=["sales_date", "active_months", "active_months"],
    )

    series_frame = build_formula_time_series(
        frame,
        time_field="sales_date",
        formula="sum(active_months)/nullif(count(active_months),0)",
        grain="month",
    )

    assert list(series_frame["period_label"]) == ["2024-01"]
    assert float(series_frame.iloc[0]["value"]) == pytest.approx(3.0)


def test_run_prediction_analysis_supports_formula_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.intelligence.predictive.load_mart_profile",
        lambda dataset_id, table: {
            "columns": [
                {"name": "sales_date", "effective_role": "temporal", "physical_type": "date"},
                {"name": "net_sales", "effective_role": "measure", "physical_type": "float"},
                {"name": "orders", "effective_role": "measure", "physical_type": "float"},
            ]
        },
    )
    monkeypatch.setattr("app.services.intelligence.predictive.resolve_time_field", lambda profile, preferred=None: "sales_date")
    monkeypatch.setattr(
        "app.services.intelligence.predictive.fetch_frame",
        lambda **kwargs: pd.DataFrame(
            {
                "sales_date": ["2024-01-01", "2024-01-15", "2024-02-01", "2024-02-15"],
                "net_sales": [100.0, 120.0, 140.0, 160.0],
                "orders": [10.0, 12.0, 14.0, 16.0],
            }
        ),
    )

    summary = run_prediction_analysis(
        PredictionSpec(
            mode="risk",
            dataset_id="silkroute",
            table="gold_sales_daily",
            metric="avg_order_value",
            display_label="Average Order Value",
            metric_source="formula",
            formula="sum(net_sales)/nullif(sum(orders),0)",
            time_field="sales_date",
            time_grain="month",
            supporting_fields=["net_sales", "orders"],
            horizon=2,
            target_value=11.0,
            target_direction="up",
        ),
        SimpleNamespace(),
    )

    assert summary.metric == "avg_order_value"
    assert summary.metric_source == "formula"
    assert summary.formula == "sum(net_sales)/nullif(sum(orders),0)"
    assert summary.points
    assert summary.confidence_score is not None
    assert summary.points[-1].is_forecast is True


def test_run_prediction_analysis_rejects_invalid_formula(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.intelligence.predictive.load_mart_profile",
        lambda dataset_id, table: {
            "columns": [
                {"name": "sales_date", "effective_role": "temporal", "physical_type": "date"},
                {"name": "net_sales", "effective_role": "measure", "physical_type": "float"},
                {"name": "orders", "effective_role": "measure", "physical_type": "float"},
            ]
        },
    )
    monkeypatch.setattr("app.services.intelligence.predictive.resolve_time_field", lambda profile, preferred=None: "sales_date")
    monkeypatch.setattr(
        "app.services.intelligence.predictive.fetch_frame",
        lambda **kwargs: pd.DataFrame({"sales_date": ["2024-01-01"], "net_sales": [100.0], "orders": [10.0]}),
    )
    with pytest.raises(HTTPException):
        run_prediction_analysis(
            PredictionSpec(
                mode="forecast",
                dataset_id="silkroute",
                table="gold_sales_daily",
                metric="bad_metric",
                metric_source="formula",
                formula="net_sales / orders",
                time_field="sales_date",
                time_grain="month",
            ),
            SimpleNamespace(),
        )
