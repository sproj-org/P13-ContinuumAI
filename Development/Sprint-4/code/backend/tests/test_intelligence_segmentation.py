from __future__ import annotations

import os
from types import SimpleNamespace

import pandas as pd
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_intelligence_segmentation.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.services.intelligence import segmentation  # noqa: E402
from app.services.intelligence.specs import SegmentSpec  # noqa: E402


def _profile() -> dict[str, object]:
    return {
        "columns": [
            {"name": "customer_id", "effective_role": "dimension", "physical_type": "text"},
            {"name": "net_sales", "effective_role": "measure", "physical_type": "float"},
            {"name": "orders", "effective_role": "measure", "physical_type": "int"},
            {"name": "avg_order_value", "effective_role": "measure", "physical_type": "float"},
        ]
    }


def test_run_segmentation_returns_assignments_and_profiles(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = pd.DataFrame(
        [
            {"customer_id": "c1", "net_sales": 120.0, "orders": 8, "avg_order_value": 15.0},
            {"customer_id": "c2", "net_sales": 135.0, "orders": 9, "avg_order_value": 15.0},
            {"customer_id": "c3", "net_sales": 150.0, "orders": 10, "avg_order_value": 15.0},
            {"customer_id": "c4", "net_sales": 480.0, "orders": 12, "avg_order_value": 40.0},
            {"customer_id": "c5", "net_sales": 510.0, "orders": 13, "avg_order_value": 39.2},
            {"customer_id": "c6", "net_sales": 540.0, "orders": 14, "avg_order_value": 38.6},
        ]
    )

    monkeypatch.setattr(segmentation, "load_mart_profile", lambda dataset_id, table: _profile())
    monkeypatch.setattr(segmentation, "resolve_entity_field", lambda profile, preferred=None: preferred or "customer_id")
    monkeypatch.setattr(
        segmentation,
        "resolve_feature_columns",
        lambda profile, preferred=None, exclude=None, limit=6: ["net_sales", "orders", "avg_order_value"],
    )
    monkeypatch.setattr(segmentation, "fetch_frame", lambda **_: frame.copy())

    summary = segmentation.run_segmentation(
        SegmentSpec(
            dataset_id="silkroute",
            table="gold_customer_360",
            entity_field="customer_id",
            features=["net_sales", "orders", "avg_order_value"],
            cluster_count=2,
        ),
        db=SimpleNamespace(),
    )

    assert summary.entity_field == "customer_id"
    assert summary.cluster_count == 2
    assert summary.features == ["net_sales", "orders", "avg_order_value"]
    assert len(summary.assignments) == 6
    assert len(summary.profiles) == 2
    assert all(profile.label for profile in summary.profiles)
    assert all(profile.entity_count >= 1 for profile in summary.profiles)
