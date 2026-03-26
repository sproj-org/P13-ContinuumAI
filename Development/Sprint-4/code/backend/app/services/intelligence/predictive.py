"""Lightweight predictive analytics helpers."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.intelligence.data_access import (
    aggregate_time_series,
    fetch_frame,
    load_mart_profile,
    resolve_time_field,
)
from app.services.intelligence.specs import (
    PredictionAnomaly,
    PredictionPoint,
    PredictionSpec,
    PredictionSummary,
    RiskBand,
    StrategyRiskSummary,
)


def _future_periods(last_period: pd.Timestamp, grain: str, horizon: int) -> list[pd.Timestamp]:
    freq = {
        "day": "D",
        "week": "W-MON",
        "month": "MS",
        "quarter": "QS",
        "year": "YS",
    }[grain]
    start = (pd.Timestamp(last_period) + pd.tseries.frequencies.to_offset(freq)).normalize()
    return list(pd.date_range(start=start, periods=horizon, freq=freq))


def _period_label(value: pd.Timestamp, grain: str) -> str:
    ts = pd.Timestamp(value)
    if grain == "month":
        return ts.strftime("%Y-%m")
    if grain == "quarter":
        return str(ts.to_period("Q"))
    if grain == "year":
        return ts.strftime("%Y")
    return ts.strftime("%Y-%m-%d")


def build_forecast(values: list[float], *, horizon: int) -> tuple[list[float], list[float], list[float], float | None]:
    if not values:
        return [], [], [], None

    history = np.asarray(values, dtype=float)
    if len(history) == 1:
        forecast = [float(history[0])] * horizon
        return forecast, forecast, forecast, 0.0

    x = np.arange(len(history), dtype=float)
    slope, intercept = np.polyfit(x, history, deg=1)
    window = max(3, min(6, len(history)))
    rolling_mean = float(np.mean(history[-window:]))
    trend_history = intercept + slope * x
    residuals = history - trend_history
    residual_std = float(np.std(residuals)) if len(residuals) > 1 else max(float(np.std(history)), 0.0)
    volatility = max(residual_std, abs(rolling_mean) * 0.05)
    non_negative = bool(np.nanmin(history) >= 0)

    forecast_values: list[float] = []
    lower_bounds: list[float] = []
    upper_bounds: list[float] = []
    for step in range(1, horizon + 1):
        next_index = len(history) - 1 + step
        trend_component = float(intercept + slope * next_index)
        blended = (0.65 * trend_component) + (0.35 * rolling_mean)
        if non_negative:
            blended = max(blended, 0.0)
        forecast_values.append(blended)
        lower = blended - volatility
        upper = blended + volatility
        if non_negative:
            lower = max(lower, 0.0)
        lower_bounds.append(lower)
        upper_bounds.append(upper)

    projected_change_pct = None
    if history[-1] not in (0.0, -0.0):
        projected_change_pct = float((forecast_values[-1] - history[-1]) / abs(history[-1]))
    return forecast_values, lower_bounds, upper_bounds, projected_change_pct


def detect_series_anomalies(
    labels: list[str],
    values: list[float],
    *,
    sensitivity: float,
    window: int = 5,
) -> list[PredictionAnomaly]:
    if len(values) < max(window + 1, 6):
        return []

    anomalies: list[PredictionAnomaly] = []
    series = np.asarray(values, dtype=float)
    rolling_window = min(window, len(series) - 1)
    for index in range(rolling_window, len(series)):
        baseline = series[index - rolling_window : index]
        mean = float(np.mean(baseline))
        std = float(np.std(baseline))
        if std <= 1e-9:
            std = max(abs(mean) * 0.1, 1.0)
        score = (float(series[index]) - mean) / std
        if abs(score) < sensitivity:
            continue
        severity = "high" if abs(score) >= sensitivity + 1.5 else "medium" if abs(score) >= sensitivity + 0.5 else "low"
        anomalies.append(
            PredictionAnomaly(
                label=labels[index],
                value=float(series[index]),
                deviation=float(score),
                severity=severity,
            )
        )
    return anomalies


def estimate_risk_band(
    *,
    projected_value: float | None,
    target_value: float | None,
    direction: str | None,
) -> tuple[RiskBand, float | None]:
    if projected_value is None or target_value is None or direction not in {"up", "down"}:
        return "unknown", None

    if direction == "up":
        variance = projected_value - target_value
        if projected_value >= target_value:
            return "low", variance
        if projected_value >= target_value * 0.95:
            return "medium", variance
        return "high", variance

    variance = target_value - projected_value
    if projected_value <= target_value:
        return "low", variance
    if projected_value <= target_value * 1.05:
        return "medium", variance
    return "high", variance


def summarize_prediction_from_series(
    *,
    labels: list[str],
    values: list[float],
    spec: PredictionSpec,
    last_period: pd.Timestamp | None = None,
) -> PredictionSummary:
    anomalies = detect_series_anomalies(labels, values, sensitivity=spec.sensitivity)
    points: list[PredictionPoint] = [
        PredictionPoint(
            label=label,
            actual=value,
            anomaly_flag=any(anomaly.label == label for anomaly in anomalies),
            anomaly_score=next((anomaly.deviation for anomaly in anomalies if anomaly.label == label), None),
            target_value=spec.target_value,
        )
        for label, value in zip(labels, values)
    ]

    forecast_values: list[float] = []
    lower_bounds: list[float] = []
    upper_bounds: list[float] = []
    projected_change_pct: float | None = None
    if spec.mode in {"forecast", "risk"}:
        forecast_values, lower_bounds, upper_bounds, projected_change_pct = build_forecast(values, horizon=spec.horizon)
        if last_period is not None or labels:
            try:
                resolved_last_period = pd.Timestamp(last_period) if last_period is not None else pd.Timestamp(labels[-1])
            except ValueError:
                resolved_last_period = pd.Timestamp.now().normalize()
            future_labels = [_period_label(item, spec.time_grain) for item in _future_periods(resolved_last_period, spec.time_grain, spec.horizon)]
            for index, label in enumerate(future_labels):
                points.append(
                    PredictionPoint(
                        label=label,
                        forecast=float(forecast_values[index]),
                        lower=float(lower_bounds[index]),
                        upper=float(upper_bounds[index]),
                        is_forecast=True,
                        target_value=spec.target_value,
                    )
                )

    risk_band: RiskBand | None = None
    if spec.mode == "risk" or spec.target_value is not None:
        projected_terminal = forecast_values[-1] if forecast_values else (values[-1] if values else None)
        risk_band, _ = estimate_risk_band(
            projected_value=projected_terminal,
            target_value=spec.target_value,
            direction=spec.target_direction,
        )

    display_label = spec.display_label or spec.metric
    if projected_change_pct is not None:
        explanation = (
            f"Based on {len(values)} observed {spec.time_grain} periods for {display_label}, "
            f"the projected terminal change is {projected_change_pct * 100:.1f}% over the next {spec.horizon} periods."
        )
    elif anomalies:
        explanation = f"Detected {len(anomalies)} anomaly signal(s) across {len(values)} observed periods for {display_label}."
    else:
        explanation = f"Observed {len(values)} {spec.time_grain} periods for {display_label} without a strong directional break."
    return PredictionSummary(
        mode=spec.mode,
        metric=spec.metric,
        display_label=display_label,
        time_field=spec.time_field,
        time_grain=spec.time_grain,
        horizon=spec.horizon,
        points=points,
        anomalies=anomalies,
        observed_points=len(values),
        historical_start=labels[0] if labels else None,
        historical_end=labels[-1] if labels else None,
        projected_change_pct=projected_change_pct,
        risk_band=risk_band,
        target_value=spec.target_value,
        target_direction=spec.target_direction,
        explanation=explanation,
    )


def run_prediction_analysis(spec: PredictionSpec, db: Session) -> PredictionSummary:
    profile = load_mart_profile(spec.dataset_id or "silkroute", spec.table)
    time_field = resolve_time_field(profile, spec.time_field)
    if not time_field:
        raise HTTPException(status_code=422, detail="No temporal field is available for predictive analysis")

    frame = fetch_frame(
        dataset_id=spec.dataset_id or "silkroute",
        table=spec.table,
        columns=[time_field, spec.metric, *spec.group_by],
        filters=spec.filters,
        db=db,
        limit=20000,
    )
    series_frame = aggregate_time_series(
        frame,
        time_field=time_field,
        metric=spec.metric,
        aggregation=spec.aggregation,
        grain=spec.time_grain,
        group_by=[],
    )
    if series_frame.empty:
        raise HTTPException(status_code=404, detail="No rows are available for predictive analysis")

    labels = [str(item) for item in series_frame["period_label"].tolist()]
    values = [float(item) for item in series_frame["value"].tolist()]
    normalized_spec = spec.model_copy(update={"time_field": time_field})
    return summarize_prediction_from_series(
        labels=labels,
        values=values,
        spec=normalized_spec,
        last_period=pd.Timestamp(series_frame["period_start"].iloc[-1]),
    )


def build_strategy_risk_summary(
    *,
    kpi_id: str,
    kpi_label: str | None,
    target_value: float | None,
    current_value: float | None,
    prediction: PredictionSummary | None,
    direction: str | None,
    target_horizon: str | None = None,
    recommended_actions: list[str] | None = None,
    supporting_details: list[str] | None = None,
) -> StrategyRiskSummary:
    projected_value = None
    if prediction and prediction.points:
        projected_candidates = [point.forecast for point in prediction.points if point.is_forecast and point.forecast is not None]
        projected_value = projected_candidates[-1] if projected_candidates else None
    risk_band, variance_to_target = estimate_risk_band(
        projected_value=projected_value,
        target_value=target_value,
        direction=direction,
    )
    return StrategyRiskSummary(
        kpi_id=kpi_id,
        kpi_label=kpi_label,
        target_value=target_value,
        current_value=current_value,
        projected_value=projected_value,
        variance_to_target=variance_to_target,
        direction=direction if direction in {"up", "down"} else None,
        risk_band=risk_band,
        explanation=(
            f"Projected terminal value is {projected_value:.2f} against target {target_value:.2f}."
            if projected_value is not None and target_value is not None
            else "Insufficient target or forecast data to estimate risk with confidence."
        ),
        target_horizon=target_horizon,
        forecast_basis=prediction.explanation if prediction is not None else None,
        recommended_actions=[item for item in (recommended_actions or []) if item],
        supporting_details=[item for item in (supporting_details or []) if item],
    )
