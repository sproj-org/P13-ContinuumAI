from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_strategy_targets.db"
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
def strategy_targets_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    _patch_storage_paths(monkeypatch, tmp_path)
    storage.ensure_strategy_config_initialized()

    # seed one KPI so targets validation can pass
    storage.write_yaml(
        storage.BASE_KPI_PATH,
        {
            "schema_version": 1,
            "version": "1.0.0",
            "kpis": [
                {
                    "id": "sales_growth",
                    "description": "Sales growth",
                    "formula": "sum(net_sales)",
                    "marts": [],
                    "required_columns": [],
                    "dimensions": [],
                }
            ],
            "aliases": {},
            "derived_metrics": {},
        },
    )

    app = FastAPI()
    app.include_router(bundle_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")
    return TestClient(app)


def test_targets_crud(strategy_targets_client: TestClient) -> None:
    fetched = strategy_targets_client.get("/api/strategy/targets")
    assert fetched.status_code == 200
    start = fetched.json()
    assert start["revision"] == "r0001"
    assert start["targets"] == []
    assert "sales_growth" in start["available_kpis"]

    created = strategy_targets_client.post(
        "/api/strategy/targets",
        json={
            "expected_revision": start["revision"],
            "target": {
                "kpi_id": "sales_growth",
                "target_value": 0.12,
                "yellow_threshold": 0.05,
                "red_threshold": 0.02,
                "direction": "up",
                "owner": "strategy",
                "horizon": "quarter",
            },
            "author": "tester",
            "reason": "add target",
        },
    )
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["revision"] == "r0002"
    assert created_payload["targets"][0]["kpi_id"] == "sales_growth"

    updated = strategy_targets_client.put(
        "/api/strategy/targets/sales_growth",
        json={
            "expected_revision": created_payload["revision"],
            "target": {
                "kpi_id": "sales_growth",
                "target_value": 0.15,
                "yellow_threshold": 0.08,
                "red_threshold": 0.03,
                "direction": "up",
                "owner": "finance",
                "horizon": "year",
            },
            "author": "tester",
            "reason": "update target",
        },
    )
    assert updated.status_code == 200
    updated_payload = updated.json()
    assert updated_payload["revision"] == "r0003"
    assert updated_payload["targets"][0]["target_value"] == 0.15

    deleted = strategy_targets_client.request(
        "DELETE",
        "/api/strategy/targets/sales_growth",
        json={
            "expected_revision": updated_payload["revision"],
            "author": "tester",
            "reason": "remove target",
        },
    )
    assert deleted.status_code == 200
    deleted_payload = deleted.json()
    assert deleted_payload["revision"] == "r0004"
    assert deleted_payload["targets"] == []


def test_targets_conflict(strategy_targets_client: TestClient) -> None:
    fetched = strategy_targets_client.get("/api/strategy/targets")
    assert fetched.status_code == 200
    revision = fetched.json()["revision"]

    first = strategy_targets_client.post(
        "/api/strategy/targets",
        json={
            "expected_revision": revision,
            "target": {
                "kpi_id": "sales_growth",
                "target_value": 0.12,
                "direction": "up",
            },
            "author": "tester",
            "reason": "first",
        },
    )
    assert first.status_code == 200

    stale = strategy_targets_client.post(
        "/api/strategy/targets",
        json={
            "expected_revision": revision,
            "target": {
                "kpi_id": "sales_growth",
                "target_value": 0.2,
                "direction": "up",
            },
            "author": "tester",
            "reason": "stale",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "REVISION_CONFLICT"
