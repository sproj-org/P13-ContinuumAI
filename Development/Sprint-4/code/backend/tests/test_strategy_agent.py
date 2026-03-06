from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_strategy_agent.db"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.api.strategy import bundle_router
from app.api.strategy_agent import router as strategy_agent_router
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
def strategy_agent_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    _patch_storage_paths(monkeypatch, tmp_path)
    storage.ensure_strategy_config_initialized()

    snapshot = DatasetSchemaSnapshot(
        dataset_id="silkroute",
        available_marts={"gold_sales_daily", "gold_store_360"},
        mart_columns={
            "gold_sales_daily": {"net_sales", "order_id", "store_id", "sales_date"},
            "gold_store_360": {"store_id", "region"},
        },
    )
    monkeypatch.setattr("app.api.strategy.load_dataset_schema", lambda dataset_id: snapshot)
    monkeypatch.setattr("app.api.strategy_agent.load_dataset_schema", lambda dataset_id: snapshot)
    monkeypatch.setattr(
        "app.services.strategy.agent._openai_extract_candidates",
        lambda text, dataset_snapshot: (None, ["OpenAI disabled in tests; used heuristic extraction."]),
    )

    app = FastAPI()
    app.include_router(bundle_router, prefix="/api")
    app.include_router(strategy_agent_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")
    return TestClient(app)


def test_extract_kpis_heuristic_path(strategy_agent_client: TestClient) -> None:
    response = strategy_agent_client.post(
        "/api/strategy/agent/extract-kpis",
        json={
            "dataset_id": "silkroute",
            "text": "Prioritize sales growth and transactions this quarter.",
            "expected_revision": "r0001",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["revision"] == "r0001"
    assert len(payload["candidates"]) >= 1
    candidate_ids = {item["id"] for item in payload["candidates"]}
    assert "total_sales" in candidate_ids or "transactions" in candidate_ids
    assert any("heuristic" in note.lower() for note in payload["notes"])


def test_reconcile_reports_missing_dependencies(strategy_agent_client: TestClient) -> None:
    response = strategy_agent_client.post(
        "/api/strategy/agent/reconcile",
        json={
            "dataset_id": "silkroute",
            "expected_revision": "r0001",
            "candidates": [
                {
                    "id": "returns_rate",
                    "description": "Returns rate",
                    "formula": "sum(revenue) / nullif(sum(net_sales), 0)",
                    "marts": ["gold_sales_daily"],
                    "required_columns": ["revenue", "net_sales"],
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["revision"] == "r0001"
    assert len(payload["missing"]) == 1
    assert payload["missing"][0]["kpi_id"] == "returns_rate"
    assert len(payload["missing_dependencies"]) == 1
    assert payload["missing_dependencies"][0]["kpi_id"] == "returns_rate"
    assert len(payload["candidates"]) == 1
    assert payload["candidates"][0]["id"] == "returns_rate"
    assert any(item["kpi_id"] == "returns_rate" for item in payload["column_matches"])


def test_apply_patch_conflict(strategy_agent_client: TestClient) -> None:
    start = strategy_agent_client.get("/api/strategy/kpis", params={"dataset_id": "silkroute"})
    assert start.status_code == 200
    current_revision = start.json()["revision"]

    apply_ok = strategy_agent_client.post(
        "/api/strategy/agent/apply",
        json={
            "dataset_id": "silkroute",
            "expected_revision": current_revision,
            "author": "tester",
            "reason": "seed kpi",
            "patch": {
                "op": "upsert_kpis",
                "kpis": [
                    {
                        "id": "sales_total",
                        "description": "Sales total",
                        "formula": "sum(net_sales)",
                        "marts": ["gold_sales_daily"],
                        "required_columns": ["net_sales"],
                    }
                ],
            },
        },
    )
    assert apply_ok.status_code == 200
    assert apply_ok.json()["revision"] == "r0002"

    apply_stale = strategy_agent_client.post(
        "/api/strategy/agent/apply",
        json={
            "dataset_id": "silkroute",
            "expected_revision": current_revision,
            "author": "tester",
            "reason": "stale write",
            "patch": {
                "op": "upsert_kpis",
                "kpis": [
                    {
                        "id": "sales_total_2",
                        "description": "Sales total 2",
                        "formula": "sum(net_sales)",
                        "marts": ["gold_sales_daily"],
                        "required_columns": ["net_sales"],
                    }
                ],
            },
        },
    )
    assert apply_stale.status_code == 409
    detail = apply_stale.json()["detail"]
    assert detail["code"] == "REVISION_CONFLICT"
