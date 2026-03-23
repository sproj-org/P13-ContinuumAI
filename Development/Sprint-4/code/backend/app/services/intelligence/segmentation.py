"""Small-model segmentation helpers using lightweight numpy routines."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.intelligence.data_access import (
    fetch_frame,
    load_mart_profile,
    resolve_entity_field,
    resolve_feature_columns,
)
from app.services.intelligence.specs import SegmentAssignment, SegmentProfile, SegmentSpec, SegmentSummary

DEFAULT_FEATURE_HINTS: dict[str, list[str]] = {
    "gold_customer_360": ["net_sales", "orders", "avg_order_value", "active_months", "frequency_per_month", "recency_days"],
    "gold_store_360": ["net_sales", "orders", "avg_order_value", "channel_mix_online_pct", "net_sales_28d_growth_pct"],
    "gold_product_360": ["net_sales", "orders", "units_sold", "avg_selling_price", "store_coverage", "return_rate_amount"],
    "gold_inventory_health_daily": ["stock_on_hand", "units_28d", "adj_avg_daily_units", "adj_days_of_inventory", "reorder_qty_suggestion"],
    "gold_employee_360": ["net_sales", "orders", "avg_order_value", "discount_ratio", "return_rate_amount"],
}


def _standardize(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    means = values.mean(axis=0)
    stds = values.std(axis=0)
    stds[stds == 0] = 1.0
    return (values - means) / stds, means, stds


def kmeans_cluster(values: np.ndarray, cluster_count: int, *, max_iter: int = 30, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    if len(values) < cluster_count:
        raise ValueError("cluster_count exceeds available rows")

    rng = np.random.default_rng(seed)
    initial_indexes = np.linspace(0, len(values) - 1, cluster_count, dtype=int)
    centers = values[initial_indexes].copy()
    if len(np.unique(initial_indexes)) != cluster_count:
        centers = values[rng.choice(len(values), size=cluster_count, replace=False)].copy()

    labels = np.zeros(len(values), dtype=int)
    for _ in range(max_iter):
        distances = np.linalg.norm(values[:, None, :] - centers[None, :, :], axis=2)
        next_labels = distances.argmin(axis=1)
        if np.array_equal(labels, next_labels):
            break
        labels = next_labels
        for cluster_id in range(cluster_count):
            members = values[labels == cluster_id]
            if len(members) == 0:
                centers[cluster_id] = values[rng.integers(0, len(values))]
            else:
                centers[cluster_id] = members.mean(axis=0)
    return labels, centers


def project_2d(values: np.ndarray) -> np.ndarray:
    if values.shape[1] <= 2:
        if values.shape[1] == 1:
            return np.column_stack([values[:, 0], np.zeros(len(values))])
        return values[:, :2]
    centered = values - values.mean(axis=0, keepdims=True)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    components = vt[:2].T
    return centered @ components


def _silhouette_hint(values: np.ndarray, labels: np.ndarray, centers: np.ndarray) -> float | None:
    if len(np.unique(labels)) < 2:
        return None
    within = 0.0
    for cluster_id in np.unique(labels):
        members = values[labels == cluster_id]
        within += float(np.mean(np.linalg.norm(members - centers[cluster_id], axis=1)))
    between = float(np.mean(np.linalg.norm(centers[:, None, :] - centers[None, :, :], axis=2)))
    if between <= 1e-9:
        return None
    return round(max(min((between - within) / between, 1.0), -1.0), 3)


def _profile_label(feature_names: list[str], centroid: dict[str, float], overall_means: dict[str, float]) -> tuple[str, list[str]]:
    ranked = sorted(
        (
            (feature, centroid.get(feature, 0.0) - overall_means.get(feature, 0.0))
            for feature in feature_names
        ),
        key=lambda item: abs(item[1]),
        reverse=True,
    )
    highlights: list[str] = []
    descriptors: list[str] = []
    for feature, delta in ranked[:2]:
        direction = "higher" if delta >= 0 else "lower"
        highlights.append(f"{feature} is {direction} than average")
        descriptors.append(f"{direction} {feature}")
    label = " / ".join(descriptors) if descriptors else "Balanced cluster"
    return label.title(), highlights


def run_segmentation(spec: SegmentSpec, db: Session) -> SegmentSummary:
    dataset_id = spec.dataset_id or "silkroute"
    profile = load_mart_profile(dataset_id, spec.table)
    entity_field = resolve_entity_field(profile, spec.entity_field)
    if not entity_field:
        raise HTTPException(status_code=422, detail="No suitable entity field is available for segmentation")

    preferred_features = spec.features or DEFAULT_FEATURE_HINTS.get(spec.table, [])
    feature_columns = resolve_feature_columns(
        profile,
        preferred=preferred_features,
        exclude={entity_field},
        limit=6,
    )
    if len(feature_columns) < 2:
        raise HTTPException(status_code=422, detail="At least two numeric features are required for segmentation")

    frame = fetch_frame(
        dataset_id=dataset_id,
        table=spec.table,
        columns=[entity_field, *feature_columns],
        filters=spec.filters,
        db=db,
        limit=20000,
    )
    if frame.empty:
        raise HTTPException(status_code=404, detail="No rows are available for segmentation")

    grouped = frame.groupby(entity_field, dropna=True)[feature_columns].mean(numeric_only=True).reset_index()
    grouped = grouped.dropna(subset=feature_columns, how="all")
    if len(grouped) < 4:
        raise HTTPException(status_code=422, detail="Not enough entity rows are available for segmentation")

    feature_frame = grouped[feature_columns].apply(pd.to_numeric, errors="coerce")
    feature_frame = feature_frame.fillna(feature_frame.median(numeric_only=True))
    grouped[feature_columns] = feature_frame

    actual_cluster_count = min(spec.cluster_count, max(2, len(grouped) // 2))
    values = feature_frame.to_numpy(dtype=float)
    standardized, _, _ = _standardize(values)
    labels, centers = kmeans_cluster(standardized, actual_cluster_count)
    projection = project_2d(standardized)
    silhouette_hint = _silhouette_hint(standardized, labels, centers)

    feature_names = list(feature_frame.columns)
    overall_means = {column: float(feature_frame[column].mean()) for column in feature_names}
    assignments: list[SegmentAssignment] = []
    profiles: list[SegmentProfile] = []

    for row_index, (_, row) in enumerate(grouped.iterrows()):
        assignments.append(
            SegmentAssignment(
                entity_id=str(row[entity_field]),
                cluster_id=int(labels[row_index]),
                projection_x=float(projection[row_index, 0]),
                projection_y=float(projection[row_index, 1]),
                feature_values={column: float(row[column]) for column in feature_names},
            )
        )

    for cluster_id in range(actual_cluster_count):
        members = grouped[labels == cluster_id]
        centroid = {column: float(members[column].mean()) for column in feature_names}
        label, highlights = _profile_label(feature_names, centroid, overall_means)
        profiles.append(
            SegmentProfile(
                cluster_id=cluster_id,
                label=label,
                entity_count=int(len(members)),
                centroid=centroid,
                metric_highlights=highlights,
            )
        )

    profiles.sort(key=lambda item: item.cluster_id)
    assignments.sort(key=lambda item: (item.cluster_id, item.entity_id))
    return SegmentSummary(
        entity_field=entity_field,
        cluster_count=actual_cluster_count,
        features=feature_names,
        assignments=assignments,
        profiles=profiles,
        silhouette_hint=silhouette_hint,
    )
