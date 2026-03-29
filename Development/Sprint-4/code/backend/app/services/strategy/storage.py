"""Task-2 strategy artifact storage with file-based revisions."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from app.models.kpi_registry import KPIRegistry
from app.models.strategy_bundle import StrategyBundle
from app.services.strategy.errors import (
    StrategyRevisionConflictError,
    StrategyValidationError,
    StrategyYamlParseError,
)

BACKEND_ROOT = Path(__file__).resolve().parents[3]
STRATEGY_CONFIG_DIR = BACKEND_ROOT / "strategy_config"
OVERRIDES_DIR = STRATEGY_CONFIG_DIR / "overrides"
REVISIONS_DIR = STRATEGY_CONFIG_DIR / "revisions"

BASE_STRATEGY_PATH = STRATEGY_CONFIG_DIR / "strategy_bundle.yaml"
BASE_KPI_PATH = STRATEGY_CONFIG_DIR / "kpi_registry.yaml"
OVERRIDE_STRATEGY_PATH = OVERRIDES_DIR / "strategy_bundle.override.yaml"
OVERRIDE_KPI_PATH = OVERRIDES_DIR / "kpi_registry.override.yaml"
REVISION_INDEX_PATH = REVISIONS_DIR / "index.json"

StrategyArtifactMode = Literal["base", "override"]

_LOCK = RLock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _revision_id(number: int) -> str:
    return f"r{number:04d}"


def _default_strategy_bundle() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "version": "1.0.0",
        "strategic_context": {
            "company": "Demo Company",
            "horizon": "12 months",
            "north_star_metric": "net_sales_after_returns",
            "narrative": "Baseline strategy bundle for Sprint-4 Task 2.",
        },
        "pillars": [
            {
                "id": "growth",
                "description": "Drive profitable growth in core segments.",
                "owner": "strategy",
            }
        ],
        "swot": {
            "strengths": [],
            "weaknesses": [],
            "opportunities": [],
            "threats": [],
        },
        "targets": {},
        "decision_rules": [],
        "scoring_model": {
            "weights": {
                "kpi_coverage": 0.4,
                "rule_readiness": 0.2,
                "hierarchy_readiness": 0.2,
                "data_readiness": 0.2,
            }
        },
    }


def _default_kpi_registry() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "version": "1.0.0",
        "kpis": [],
        "aliases": {},
        "derived_metrics": {},
    }


def _yaml_dump_text(payload: dict[str, Any]) -> str:
    rendered = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
    return rendered if rendered.endswith("\n") else rendered + "\n"


def _read_revision_index_unchecked() -> dict[str, int]:
    if not REVISION_INDEX_PATH.exists():
        return {"last_revision": 0}
    try:
        payload = json.loads(REVISION_INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"last_revision": 0}
    value = payload.get("last_revision", 0) if isinstance(payload, dict) else 0
    if not isinstance(value, int) or value < 0:
        value = 0
    return {"last_revision": value}


def _write_revision_index(index: dict[str, int]) -> None:
    REVISION_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVISION_INDEX_PATH.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")


def _current_revision_id_unlocked() -> str:
    return _revision_id(_read_revision_index_unchecked()["last_revision"])


def ensure_strategy_config_initialized() -> None:
    with _LOCK:
        STRATEGY_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        OVERRIDES_DIR.mkdir(parents=True, exist_ok=True)
        REVISIONS_DIR.mkdir(parents=True, exist_ok=True)

        if not BASE_STRATEGY_PATH.exists():
            write_yaml(BASE_STRATEGY_PATH, _default_strategy_bundle())
        if not BASE_KPI_PATH.exists():
            write_yaml(BASE_KPI_PATH, _default_kpi_registry())
        if not OVERRIDE_STRATEGY_PATH.exists():
            write_yaml(OVERRIDE_STRATEGY_PATH, {})
        if not OVERRIDE_KPI_PATH.exists():
            write_yaml(OVERRIDE_KPI_PATH, {})
        if not REVISION_INDEX_PATH.exists():
            _write_revision_index({"last_revision": 0})

        index = _read_revision_index_unchecked()
        if index["last_revision"] < 1:
            index["last_revision"] = 1
            _write_revision_index(index)
            write_revision_snapshot(
                _revision_id(1),
                author="system",
                reason="bootstrap_defaults",
                base_strategy_yaml=BASE_STRATEGY_PATH.read_text(encoding="utf-8"),
                base_kpi_yaml=BASE_KPI_PATH.read_text(encoding="utf-8"),
                override_strategy_yaml=OVERRIDE_STRATEGY_PATH.read_text(encoding="utf-8"),
                override_kpi_yaml=OVERRIDE_KPI_PATH.read_text(encoding="utf-8"),
            )
            return

        revision_dir = REVISIONS_DIR / _revision_id(index["last_revision"])
        if not revision_dir.exists():
            write_revision_snapshot(
                _revision_id(index["last_revision"]),
                author="system",
                reason="repair_missing_snapshot",
                base_strategy_yaml=BASE_STRATEGY_PATH.read_text(encoding="utf-8"),
                base_kpi_yaml=BASE_KPI_PATH.read_text(encoding="utf-8"),
                override_strategy_yaml=OVERRIDE_STRATEGY_PATH.read_text(encoding="utf-8"),
                override_kpi_yaml=OVERRIDE_KPI_PATH.read_text(encoding="utf-8"),
            )


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise StrategyValidationError(f"Invalid YAML in {path.name}: {exc}") from exc
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise StrategyValidationError(f"Expected YAML object in {path.name}")
    return payload


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_yaml_dump_text(payload), encoding="utf-8")


def merge_dicts(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for key, override_value in override.items():
            if key in merged:
                merged[key] = merge_dicts(merged[key], override_value)
            else:
                merged[key] = override_value
        return merged
    return override


def get_revision_index() -> dict[str, int]:
    ensure_strategy_config_initialized()
    with _LOCK:
        return dict(_read_revision_index_unchecked())


def get_current_revision_id() -> str:
    ensure_strategy_config_initialized()
    with _LOCK:
        return _current_revision_id_unlocked()


def write_revision_snapshot(
    new_revision_id: str,
    author: str,
    reason: str,
    base_strategy_yaml: str,
    base_kpi_yaml: str,
    override_strategy_yaml: str,
    override_kpi_yaml: str,
) -> None:
    revision_dir = REVISIONS_DIR / new_revision_id
    revision_dir.mkdir(parents=True, exist_ok=True)

    (revision_dir / "strategy_bundle.yaml").write_text(base_strategy_yaml, encoding="utf-8")
    (revision_dir / "kpi_registry.yaml").write_text(base_kpi_yaml, encoding="utf-8")
    (revision_dir / "strategy_bundle.override.yaml").write_text(override_strategy_yaml, encoding="utf-8")
    (revision_dir / "kpi_registry.override.yaml").write_text(override_kpi_yaml, encoding="utf-8")

    metadata = {
        "revision": new_revision_id,
        "created_at": _utc_now_iso(),
        "author": author,
        "reason": reason,
        "hashes": {
            "strategy_bundle.yaml": _sha256_text(base_strategy_yaml),
            "kpi_registry.yaml": _sha256_text(base_kpi_yaml),
            "strategy_bundle.override.yaml": _sha256_text(override_strategy_yaml),
            "kpi_registry.override.yaml": _sha256_text(override_kpi_yaml),
        },
    }
    (revision_dir / "meta.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def bump_revision(author: str, reason: str) -> str:
    ensure_strategy_config_initialized()
    with _LOCK:
        index = _read_revision_index_unchecked()
        new_number = index["last_revision"] + 1
        new_revision_id = _revision_id(new_number)

        write_revision_snapshot(
            new_revision_id,
            author=author,
            reason=reason,
            base_strategy_yaml=BASE_STRATEGY_PATH.read_text(encoding="utf-8"),
            base_kpi_yaml=BASE_KPI_PATH.read_text(encoding="utf-8"),
            override_strategy_yaml=OVERRIDE_STRATEGY_PATH.read_text(encoding="utf-8"),
            override_kpi_yaml=OVERRIDE_KPI_PATH.read_text(encoding="utf-8"),
        )
        index["last_revision"] = new_number
        _write_revision_index(index)
        return new_revision_id


def _validate_strategy_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = StrategyBundle.model_validate(payload)
    except ValidationError as exc:
        raise StrategyValidationError(str(exc)) from exc
    return validated.model_dump(mode="python")


def _validate_kpi_registry(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = KPIRegistry.model_validate(payload)
    except ValidationError as exc:
        raise StrategyValidationError(str(exc)) from exc
    return validated.model_dump(mode="python")


def load_current_artifacts() -> tuple[dict[str, Any], dict[str, Any], str]:
    ensure_strategy_config_initialized()
    with _LOCK:
        base_strategy = load_yaml(BASE_STRATEGY_PATH)
        override_strategy = load_yaml(OVERRIDE_STRATEGY_PATH)
        merged_strategy = merge_dicts(base_strategy, override_strategy)
        validated_strategy = _validate_strategy_bundle(merged_strategy)

        base_kpi = load_yaml(BASE_KPI_PATH)
        override_kpi = load_yaml(OVERRIDE_KPI_PATH)
        merged_kpi = merge_dicts(base_kpi, override_kpi)
        validated_kpi = _validate_kpi_registry(merged_kpi)

        return validated_strategy, validated_kpi, _current_revision_id_unlocked()


def parse_yaml_text(raw_yaml: str) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        raise StrategyYamlParseError(f"Invalid YAML payload: {exc}") from exc
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise StrategyYamlParseError("YAML payload must be an object at the root.")
    return payload


def get_strategy_yaml_texts() -> tuple[str, str]:
    ensure_strategy_config_initialized()
    with _LOCK:
        return (
            BASE_STRATEGY_PATH.read_text(encoding="utf-8"),
            OVERRIDE_STRATEGY_PATH.read_text(encoding="utf-8"),
        )


def get_kpi_registry_yaml_texts() -> tuple[str, str]:
    ensure_strategy_config_initialized()
    with _LOCK:
        return (
            BASE_KPI_PATH.read_text(encoding="utf-8"),
            OVERRIDE_KPI_PATH.read_text(encoding="utf-8"),
        )


def _require_revision_match(expected_revision: str) -> None:
    current_revision = _current_revision_id_unlocked()
    if expected_revision != current_revision:
        raise StrategyRevisionConflictError(
            f"Expected revision '{expected_revision}' does not match current revision '{current_revision}'."
        )


def update_strategy_bundle(
    *,
    mode: StrategyArtifactMode,
    raw_yaml: str,
    expected_revision: str,
    author: str,
    reason: str,
) -> tuple[dict[str, Any], str]:
    payload = parse_yaml_text(raw_yaml)
    ensure_strategy_config_initialized()

    with _LOCK:
        _require_revision_match(expected_revision)

        base = load_yaml(BASE_STRATEGY_PATH)
        override = load_yaml(OVERRIDE_STRATEGY_PATH)
        merged_candidate = merge_dicts(payload, override) if mode == "base" else merge_dicts(base, payload)
        validated = _validate_strategy_bundle(merged_candidate)

        if mode == "base":
            write_yaml(BASE_STRATEGY_PATH, payload)
        else:
            write_yaml(OVERRIDE_STRATEGY_PATH, payload)

        new_revision = bump_revision(author=author, reason=reason)
        return validated, new_revision


def update_kpi_registry(
    *,
    mode: StrategyArtifactMode,
    raw_yaml: str,
    expected_revision: str,
    author: str,
    reason: str,
) -> tuple[dict[str, Any], str]:
    payload = parse_yaml_text(raw_yaml)
    ensure_strategy_config_initialized()

    with _LOCK:
        _require_revision_match(expected_revision)

        base = load_yaml(BASE_KPI_PATH)
        override = load_yaml(OVERRIDE_KPI_PATH)
        merged_candidate = merge_dicts(payload, override) if mode == "base" else merge_dicts(base, payload)
        validated = _validate_kpi_registry(merged_candidate)

        if mode == "base":
            write_yaml(BASE_KPI_PATH, payload)
        else:
            write_yaml(OVERRIDE_KPI_PATH, payload)

        new_revision = bump_revision(author=author, reason=reason)
        return validated, new_revision


def commit_base_artifacts(
    *,
    base_strategy_payload: dict[str, Any],
    base_kpi_payload: dict[str, Any],
    expected_revision: str,
    author: str,
    reason: str,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    ensure_strategy_config_initialized()
    with _LOCK:
        _require_revision_match(expected_revision)

        override_strategy = load_yaml(OVERRIDE_STRATEGY_PATH)
        override_kpi = load_yaml(OVERRIDE_KPI_PATH)

        merged_strategy = merge_dicts(base_strategy_payload, override_strategy)
        merged_kpi = merge_dicts(base_kpi_payload, override_kpi)

        validated_strategy = _validate_strategy_bundle(merged_strategy)
        validated_kpi = _validate_kpi_registry(merged_kpi)

        write_yaml(BASE_STRATEGY_PATH, base_strategy_payload)
        write_yaml(BASE_KPI_PATH, base_kpi_payload)

        new_revision = bump_revision(author=author, reason=reason)
        return validated_strategy, validated_kpi, new_revision


def restore_revision_snapshot(
    *,
    revision_to_restore: str,
    expected_revision: str,
    author: str,
    reason: str,
) -> str:
    ensure_strategy_config_initialized()
    with _LOCK:
        _require_revision_match(expected_revision)
        revision_dir = REVISIONS_DIR / revision_to_restore
        if not revision_dir.exists():
            raise StrategyValidationError(f"Revision '{revision_to_restore}' does not exist.")

        required_files = {
            "strategy_bundle.yaml": BASE_STRATEGY_PATH,
            "kpi_registry.yaml": BASE_KPI_PATH,
            "strategy_bundle.override.yaml": OVERRIDE_STRATEGY_PATH,
            "kpi_registry.override.yaml": OVERRIDE_KPI_PATH,
        }
        for source_name, destination in required_files.items():
            source_path = revision_dir / source_name
            if not source_path.exists():
                raise StrategyValidationError(
                    f"Revision '{revision_to_restore}' is missing '{source_name}'."
                )
            payload = parse_yaml_text(source_path.read_text(encoding="utf-8"))
            write_yaml(destination, payload)

        return bump_revision(author=author, reason=reason)
