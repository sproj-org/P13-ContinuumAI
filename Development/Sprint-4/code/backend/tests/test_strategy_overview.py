from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_strategy_overview.db"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.api.strategy import bundle_router
from app.core.security import get_current_user
from app.services.strategy import storage


def _patch_storage_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "strategy_config"
    monkeypatch.setattr(storage, "STRATEGY_CONFIG_DIR", config_dir)
    monkeypatch.setattr(storage, "OVERRIDES_DIR", config_dir / "overrides")
    monkeypatch.setattr(storage, "REVISIONS_DIR", config_dir / "revisions")
    monkeypatch.setattr(storage, "BASE_STRATEGY_PATH", config_dir / "strategy_bundle.yaml")
    monkeypatch.setattr(storage, "BASE_KPI_PATH", config_dir / "kpi_registry.yaml")
    monkeypatch.setattr(storage, "OVERRIDE_STRATEGY_PATH", config_dir / "overrides" / "strategy_bundle.override.yaml")
    monkeypatch.setattr(storage, "OVERRIDE_KPI_PATH", config_dir / "overrides" / "kpi_registry.override.yaml")
    monkeypatch.setattr(storage, "REVISION_INDEX_PATH", config_dir / "revisions" / "index.json")


@pytest.fixture
def strategy_overview_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    _patch_storage_paths(monkeypatch, tmp_path)
    storage.ensure_strategy_config_initialized()

    app = FastAPI()
    app.include_router(bundle_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")
    return TestClient(app)


def test_overview_get_put(strategy_overview_client: TestClient) -> None:
    fetched = strategy_overview_client.get("/api/strategy/overview")
    assert fetched.status_code == 200
    start = fetched.json()
    assert start["revision"] == "r0001"
    assert "strategy_context" in start
    assert isinstance(start["pillars"], list)

    updated = strategy_overview_client.put(
        "/api/strategy/overview",
        json={
            "expected_revision": start["revision"],
            "strategy_context": {
                "company": "Continuum AI",
                "horizon": "Q4",
                "north_star_metric": "net_sales",
                "narrative": "Focus on profitable expansion",
            },
            "pillars": [
                {"id": "growth", "description": "Grow revenue", "owner": "strategy"},
                {"id": "efficiency", "description": "Improve margin", "owner": "finance"},
            ],
            "swot": {
                "strengths": ["Brand trust"],
                "weaknesses": ["Low repeat rate"],
                "opportunities": ["Market expansion"],
                "threats": ["Price competition"],
            },
            "author": "tester",
            "reason": "update overview",
        },
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["revision"] == "r0002"
    assert payload["strategy_context"]["company"] == "Continuum AI"
    assert len(payload["pillars"]) == 2
    assert payload["swot"]["strengths"] == ["Brand trust"]


def test_overview_revision_conflict(strategy_overview_client: TestClient) -> None:
    fetched = strategy_overview_client.get("/api/strategy/overview")
    assert fetched.status_code == 200
    revision = fetched.json()["revision"]

    first = strategy_overview_client.put(
        "/api/strategy/overview",
        json={
            "expected_revision": revision,
            "strategy_context": {
                "company": "A",
                "horizon": "12m",
                "north_star_metric": "m1",
                "narrative": "n1",
            },
            "pillars": [],
            "swot": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
            "author": "tester",
            "reason": "first",
        },
    )
    assert first.status_code == 200

    stale = strategy_overview_client.put(
        "/api/strategy/overview",
        json={
            "expected_revision": revision,
            "strategy_context": {
                "company": "B",
                "horizon": "12m",
                "north_star_metric": "m1",
                "narrative": "n2",
            },
            "pillars": [],
            "swot": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
            "author": "tester",
            "reason": "stale",
        },
    )
    assert stale.status_code == 409
    detail = stale.json()["detail"]
    assert detail["code"] == "REVISION_CONFLICT"
