from __future__ import annotations

import os
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_strategy_decision_signals_api.db"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.api.strategy import bundle_router
from app.core.security import get_current_user
from app.db.database import get_db


def test_strategy_decision_signals_endpoint(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    app = FastAPI()
    app.include_router(bundle_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()

    monkeypatch.setattr(
        "app.api.strategy.build_decision_surface",
        lambda **kwargs: {
            "dataset_id": kwargs["dataset_id"],
            "revision": "r0011",
            "generated_at": "2026-03-06T00:00:00Z",
            "executive_summary": {
                "overall_readiness_score": 0.72,
                "kpis_on_track": 7,
                "kpis_warning": 3,
                "kpis_critical": 1,
                "triggered_rules": 2,
                "narrative": "Sample narrative",
            },
            "decision_signals": [
                {
                    "id": "signal_margin",
                    "title": "Margin pressure",
                    "severity": "warn",
                    "explanation": "Margin KPI is below target",
                    "suggested_action": "Review pricing and markdowns",
                }
            ],
            "recommendations": ["Review pricing and markdowns"],
        },
    )

    client = TestClient(app)
    response = client.get("/api/strategy/decision-signals", params={"dataset_id": "silkroute"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"] == "silkroute"
    assert payload["revision"] == "r0011"
    assert payload["executive_summary"]["kpis_on_track"] == 7
    assert payload["decision_signals"][0]["id"] == "signal_margin"

