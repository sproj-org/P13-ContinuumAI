from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_strategy_kpi_crud.db"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.api.strategy import bundle_router
from app.core.security import get_current_user
from app.services.strategy import storage
from app.services.strategy.schema_provider import DatasetSchemaSnapshot


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
def strategy_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    _patch_storage_paths(monkeypatch, tmp_path)
    storage.ensure_strategy_config_initialized()

    snapshot = DatasetSchemaSnapshot(
        dataset_id="silkroute",
        available_marts={"gold_sales_daily", "gold_store_360"},
        mart_columns={
            "gold_sales_daily": {"net_sales", "region", "store_id", "sales_date"},
            "gold_store_360": {"store_id", "net_sales"},
        },
    )
    monkeypatch.setattr("app.api.strategy.load_dataset_schema", lambda dataset_id: snapshot)

    app = FastAPI()
    app.include_router(bundle_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")
    return TestClient(app)


def test_kpi_crud_lifecycle(strategy_client: TestClient) -> None:
    response = strategy_client.get("/api/strategy/kpis", params={"dataset_id": "silkroute"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["revision"] == "r0001"
    assert payload["available_marts"] == ["gold_sales_daily", "gold_store_360"]
    assert "net_sales" in payload["mart_columns"]["gold_sales_daily"]

    create_body = {
        "expected_revision": payload["revision"],
        "dataset_id": "silkroute",
        "kpi": {
            "id": "sales_growth",
            "display_name": "Sales Growth",
            "description": "Growth KPI",
            "formula": "sum(net_sales)",
            "marts": ["gold_sales_daily"],
            "required_columns": ["net_sales", "region"],
            "dimensions": ["store_id"],
            "default_grain": "day",
            "pillar_id": "growth",
            "owner": "strategy",
        },
        "author": "tester",
        "reason": "add sales growth",
    }
    created = strategy_client.post("/api/strategy/kpis", json=create_body)
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["revision"] == "r0002"
    assert any(item["id"] == "sales_growth" for item in created_payload["kpis"])

    update_body = {
        "expected_revision": created_payload["revision"],
        "dataset_id": "silkroute",
        "kpi": {
            "id": "sales_growth",
            "display_name": "Sales Growth Updated",
            "description": "Updated KPI",
            "formula": "sum(net_sales)",
            "marts": ["gold_sales_daily", "gold_store_360"],
            "required_columns": ["net_sales", "store_id"],
            "dimensions": ["store_id"],
            "default_grain": "week",
            "pillar_id": "growth",
            "owner": "strategy",
        },
        "author": "tester",
        "reason": "update sales growth",
    }
    updated = strategy_client.put("/api/strategy/kpis/sales_growth", json=update_body)
    assert updated.status_code == 200
    updated_payload = updated.json()
    assert updated_payload["revision"] == "r0003"
    match = next(item for item in updated_payload["kpis"] if item["id"] == "sales_growth")
    assert match["display_name"] == "Sales Growth Updated"

    delete_body = {
        "expected_revision": updated_payload["revision"],
        "dataset_id": "silkroute",
        "author": "tester",
        "reason": "cleanup",
    }
    deleted = strategy_client.request("DELETE", "/api/strategy/kpis/sales_growth", json=delete_body)
    assert deleted.status_code == 200
    deleted_payload = deleted.json()
    assert deleted_payload["revision"] == "r0004"
    assert not any(item["id"] == "sales_growth" for item in deleted_payload["kpis"])


def test_kpi_crud_conflict(strategy_client: TestClient) -> None:
    start = strategy_client.get("/api/strategy/kpis", params={"dataset_id": "silkroute"})
    assert start.status_code == 200
    revision = start.json()["revision"]

    first_create = strategy_client.post(
        "/api/strategy/kpis",
        json={
            "expected_revision": revision,
            "dataset_id": "silkroute",
            "kpi": {
                "id": "revenue",
                "description": "Revenue KPI",
                "formula": "sum(net_sales)",
                "marts": ["gold_sales_daily"],
                "required_columns": ["net_sales"],
                "dimensions": [],
            },
            "author": "tester",
            "reason": "first write",
        },
    )
    assert first_create.status_code == 200

    stale = strategy_client.post(
        "/api/strategy/kpis",
        json={
            "expected_revision": revision,
            "dataset_id": "silkroute",
            "kpi": {
                "id": "revenue_2",
                "description": "Revenue KPI 2",
                "formula": "sum(net_sales)",
                "marts": ["gold_sales_daily"],
                "required_columns": ["net_sales"],
                "dimensions": [],
            },
            "author": "tester",
            "reason": "stale write",
        },
    )
    assert stale.status_code == 409
    detail = stale.json()["detail"]
    assert detail["code"] == "REVISION_CONFLICT"
