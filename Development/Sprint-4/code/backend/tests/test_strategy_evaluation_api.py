from __future__ import annotations

import os
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_strategy_evaluation_api.db"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.api.strategy import bundle_router
from app.core.security import get_current_user
from app.db.database import get_db


def test_strategy_evaluate_endpoint(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    app = FastAPI()
    app.include_router(bundle_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()

    monkeypatch.setattr(
        "app.api.strategy.evaluate_strategy",
        lambda **kwargs: {
            "dataset_id": kwargs["dataset_id"],
            "revision": "r0010",
            "kpis": [{"id": "sales_growth", "value": 0.09, "target": 0.1, "variance": -0.01, "status": "yellow"}],
            "triggered_rules": [],
            "evaluation_time": "2026-03-06T00:00:00Z",
        },
    )

    client = TestClient(app)
    response = client.post(
        "/api/strategy/evaluate",
        json={
            "dataset_id": "silkroute",
            "filters": [{"column": "channel", "op": "eq", "value": "Retail"}],
            "time_range": {"column": "sales_date", "from": "2025-01-01", "to": "2025-12-31"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"] == "silkroute"
    assert payload["revision"] == "r0010"
    assert payload["kpis"][0]["id"] == "sales_growth"
