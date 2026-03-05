from __future__ import annotations

from pathlib import Path

import pytest

from app.services.strategy import storage
from app.services.strategy.errors import StrategyRevisionConflictError


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


def test_merge_dicts_override_precedence() -> None:
    base = {"a": 1, "nested": {"x": 1, "y": 2}}
    override = {"nested": {"y": 99}, "new": True}
    merged = storage.merge_dicts(base, override)
    assert merged["a"] == 1
    assert merged["nested"]["x"] == 1
    assert merged["nested"]["y"] == 99
    assert merged["new"] is True


def test_revision_bootstrap_and_bump(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_storage_paths(monkeypatch, tmp_path)
    strategy, registry, revision = storage.load_current_artifacts()

    assert revision == "r0001"
    assert strategy["schema_version"] == 1
    assert registry["schema_version"] == 1
    assert (storage.REVISIONS_DIR / "r0001" / "meta.json").exists()

    new_revision = storage.bump_revision(author="tester", reason="smoke")
    assert new_revision == "r0002"
    assert (storage.REVISIONS_DIR / "r0002" / "meta.json").exists()


def test_conflict_on_stale_expected_revision(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_storage_paths(monkeypatch, tmp_path)
    current = storage.get_current_revision_id()
    assert current == "r0001"

    merged, new_revision = storage.update_strategy_bundle(
        mode="override",
        raw_yaml="targets: {}\n",
        expected_revision=current,
        author="tester",
        reason="first update",
    )
    assert new_revision == "r0002"
    assert merged["schema_version"] == 1

    with pytest.raises(StrategyRevisionConflictError):
        storage.update_strategy_bundle(
            mode="override",
            raw_yaml="targets: {}\n",
            expected_revision=current,
            author="tester",
            reason="stale update",
        )
