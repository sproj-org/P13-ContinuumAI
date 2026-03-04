"""Runtime Strategy Layer store for dataset-scoped YAML bundles."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from threading import RLock
from typing import Any

import yaml
from pydantic import ValidationError

from app.services.strategy.errors import StrategyNotFoundError, StrategyValidationError
from app.services.strategy.models import (
    DecisionRule,
    DecisionRules,
    KPIEntry,
    KPIHierarchy,
    NorthStar,
    ScoringGuardrail,
    ScoringWeight,
    StrategicContext,
    StrategyBundle,
    StrategyPillar,
    StrategyScoring,
    StrategyTargets,
)

_FILE_CONTEXT = "strategic_context.yaml"
_FILE_TARGETS = "strategy_targets.yaml"
_FILE_KPIS = "kpi_hierarchy.yaml"
_FILE_RULES = "decision_rules.yaml"
_FILE_SCORING = "strategy_scoring.yaml"

_WORD_LIMIT = 160


def _pretty_name(value: str) -> str:
    clean = value.replace("_", " ").replace("-", " ").strip()
    return " ".join(part.capitalize() for part in clean.split())


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _one_liner(value: str | None, *, fallback: str = "", limit: int = _WORD_LIMIT) -> str:
    text = (value or fallback).strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


class StrategyStore:
    """Load, validate, and memoize strategy bundles per dataset."""

    def __init__(self, base_path: Path | None = None):
        self.base_path = (
            Path(base_path)
            if base_path is not None
            else Path(__file__).resolve().parents[2] / "resources" / "strategy"
        )
        self._lock = RLock()
        self._bundle_cache: dict[str, StrategyBundle] = {}
        self._hash_cache: dict[str, str] = {}

    def _dataset_dir(self, dataset_id: str) -> Path:
        return self.base_path / dataset_id

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise StrategyValidationError(f"Missing strategy file: {path.name}")
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise StrategyValidationError(f"Invalid YAML in {path.name}: {exc}") from exc
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise StrategyValidationError(f"Expected object at root of {path.name}")
        return payload

    def _build_context(self, payload: dict[str, Any], filename: str) -> StrategicContext:
        raw = payload.get("strategic_context", payload)
        if not isinstance(raw, dict):
            raise StrategyValidationError(f"{filename} must define an object under 'strategic_context'")
        try:
            return StrategicContext.model_validate(raw)
        except ValidationError as exc:
            raise StrategyValidationError(f"{filename} failed validation: {exc}") from exc

    def _build_targets(self, payload: dict[str, Any], filename: str) -> StrategyTargets:
        raw = payload.get("strategy", payload)
        if not isinstance(raw, dict):
            raise StrategyValidationError(f"{filename} must define an object under 'strategy'")

        north_star = raw.get("north_star")
        pillars = raw.get("strategic_pillars", raw.get("pillars", []))
        model_payload = {
            "company": raw.get("company"),
            "horizon": raw.get("horizon"),
            "north_star": north_star,
            "pillars": pillars if isinstance(pillars, list) else [],
        }
        try:
            return StrategyTargets.model_validate(model_payload)
        except ValidationError as exc:
            raise StrategyValidationError(f"{filename} failed validation: {exc}") from exc

    def _kpi_entry(self, raw: dict[str, Any], *, fallback_id: str, category: str | None = None) -> KPIEntry:
        item = dict(raw)
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            name = _pretty_name(fallback_id)
            item["name"] = name

        entry_id = item.get("id")
        if not isinstance(entry_id, str) or not entry_id.strip():
            item["id"] = fallback_id
        if category and ("category" not in item or not isinstance(item.get("category"), str)):
            item["category"] = category

        return KPIEntry.model_validate(item)

    def _build_kpis(self, payload: dict[str, Any], filename: str) -> KPIHierarchy:
        raw = payload.get("kpis", payload)
        if not isinstance(raw, dict):
            raise StrategyValidationError(f"{filename} must define an object under 'kpis'")

        north_star_entry: KPIEntry | None = None
        north_star_raw = raw.get("north_star")
        if isinstance(north_star_raw, dict):
            north_star_entry = self._kpi_entry(
                north_star_raw,
                fallback_id=str(north_star_raw.get("id") or "north_star"),
                category="north_star",
            )

        kpis: list[KPIEntry] = []
        for category, items in raw.items():
            if category in {"north_star", "hierarchy"}:
                continue
            if not isinstance(items, list):
                continue
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                fallback_id = item.get("id")
                if not isinstance(fallback_id, str) or not fallback_id.strip():
                    raw_name = item.get("name")
                    if isinstance(raw_name, str) and raw_name.strip():
                        fallback_id = _slugify(raw_name)
                    else:
                        fallback_id = f"{_slugify(category)}_{index + 1}"
                try:
                    kpis.append(self._kpi_entry(item, fallback_id=fallback_id, category=category))
                except ValidationError as exc:
                    raise StrategyValidationError(f"{filename} failed KPI validation: {exc}") from exc

        hierarchy = raw.get("hierarchy") if isinstance(raw.get("hierarchy"), dict) else {}
        return KPIHierarchy(north_star=north_star_entry, kpis=kpis, hierarchy=hierarchy)

    def _severity_from_action(self, action: str | None) -> str:
        if not action:
            return "info"
        normalized = action.strip().lower()
        if "block" in normalized:
            return "block"
        if "reduce" in normalized or "penalty" in normalized:
            return "warn"
        return "info"

    def _build_rules(self, payload: dict[str, Any], filename: str) -> DecisionRules:
        raw = payload.get("decision_rules", payload)
        if not isinstance(raw, dict):
            raise StrategyValidationError(f"{filename} must define an object under 'decision_rules'")

        rules: list[DecisionRule] = []
        for group_name, group_rules in raw.items():
            if not isinstance(group_rules, list):
                continue
            for index, item in enumerate(group_rules):
                if not isinstance(item, dict):
                    continue
                rule_id = item.get("id")
                if not isinstance(rule_id, str) or not rule_id.strip():
                    rule_id = f"{_slugify(str(group_name))}_{index + 1}"

                description = item.get("description")
                if not isinstance(description, str) or not description.strip():
                    description = f"Rule for {_pretty_name(str(group_name))}"

                action = item.get("action")
                if isinstance(action, str) and action.strip():
                    guidance = str(item.get("guidance") or f"Action: {action.replace('_', ' ')}")
                else:
                    guidance = str(item.get("guidance") or "")

                applies_to = item.get("applies_to")
                if not isinstance(applies_to, list) or not applies_to:
                    applies_to = [str(group_name)]

                model_payload = {
                    **item,
                    "id": rule_id,
                    "name": str(item.get("name") or _pretty_name(rule_id)),
                    "description": description,
                    "severity": str(item.get("severity") or self._severity_from_action(action)),
                    "condition": item.get("condition"),
                    "guidance": guidance or None,
                    "applies_to": applies_to,
                    "action": action,
                }
                try:
                    rules.append(DecisionRule.model_validate(model_payload))
                except ValidationError as exc:
                    raise StrategyValidationError(f"{filename} failed rule validation: {exc}") from exc
        return DecisionRules(rules=rules)

    def _build_scoring(self, payload: dict[str, Any], filename: str) -> StrategyScoring:
        raw = payload.get("strategy_scoring", payload)
        if not isinstance(raw, dict):
            raise StrategyValidationError(f"{filename} must define an object under 'strategy_scoring'")

        scoring_model = raw.get("scoring_model")
        if isinstance(scoring_model, dict):
            scoring_model_type = str(scoring_model.get("type")) if scoring_model.get("type") is not None else None
        elif isinstance(scoring_model, str):
            scoring_model_type = scoring_model
        else:
            scoring_model_type = None

        weights: list[ScoringWeight] = []
        weights_raw = raw.get("weights")
        if isinstance(weights_raw, dict):
            for key, value in weights_raw.items():
                if not isinstance(key, str) or not isinstance(value, (int, float)):
                    continue
                weights.append(
                    ScoringWeight(
                        id=_slugify(key),
                        name=_pretty_name(key),
                        weight=float(value),
                    )
                )
        elif isinstance(weights_raw, list):
            for index, item in enumerate(weights_raw):
                if not isinstance(item, dict):
                    continue
                try:
                    weights.append(
                        ScoringWeight(
                            id=str(item.get("id") or f"weight_{index + 1}"),
                            name=str(item.get("name") or _pretty_name(str(item.get("id") or f"weight_{index + 1}"))),
                            weight=float(item.get("weight", 0.0)),
                            description=item.get("description"),
                        )
                    )
                except (TypeError, ValueError) as exc:
                    raise StrategyValidationError(f"{filename} has invalid scoring weight entry: {item}") from exc

        guardrails: list[ScoringGuardrail] = []
        guardrails_raw = raw.get("guardrails")
        if isinstance(guardrails_raw, list):
            for index, item in enumerate(guardrails_raw):
                guardrail_id = f"guardrail_{index + 1}"
                if isinstance(item, str):
                    guardrails.append(
                        ScoringGuardrail(
                            id=guardrail_id,
                            name=f"Guardrail {index + 1}",
                            rule=item,
                            severity="warn",
                        )
                    )
                    continue
                if isinstance(item, dict):
                    if {"id", "name", "rule"}.issubset(item.keys()):
                        severity = str(item.get("severity") or "warn")
                        guardrails.append(
                            ScoringGuardrail(
                                id=str(item["id"]),
                                name=str(item["name"]),
                                rule=str(item["rule"]),
                                severity=severity if severity in {"info", "warn", "block"} else "warn",
                            )
                        )
                        continue
                    if len(item) == 1:
                        condition, outcome = next(iter(item.items()))
                        if isinstance(outcome, dict):
                            outcome_text = ", ".join(f"{k}={v}" for k, v in outcome.items())
                        else:
                            outcome_text = str(outcome)
                        guardrails.append(
                            ScoringGuardrail(
                                id=guardrail_id,
                                name=_pretty_name(str(condition)),
                                rule=f"{condition} -> {outcome_text}",
                                severity="block" if "final_score = 0" in outcome_text else "warn",
                            )
                        )

        return StrategyScoring(
            scoring_model_type=scoring_model_type,
            weights=weights,
            guardrails=guardrails,
        )

    def _bundle_uncached(self, dataset_id: str) -> StrategyBundle:
        dataset_dir = self._dataset_dir(dataset_id)
        if not dataset_dir.exists() or not dataset_dir.is_dir():
            raise StrategyNotFoundError(f"No strategy layer configured for dataset '{dataset_id}'")

        context_payload = self._load_yaml(dataset_dir / _FILE_CONTEXT)
        targets_payload = self._load_yaml(dataset_dir / _FILE_TARGETS)
        kpi_payload = self._load_yaml(dataset_dir / _FILE_KPIS)
        rules_payload = self._load_yaml(dataset_dir / _FILE_RULES)
        scoring_payload = self._load_yaml(dataset_dir / _FILE_SCORING)

        return StrategyBundle(
            context=self._build_context(context_payload, _FILE_CONTEXT),
            targets=self._build_targets(targets_payload, _FILE_TARGETS),
            kpis=self._build_kpis(kpi_payload, _FILE_KPIS),
            rules=self._build_rules(rules_payload, _FILE_RULES),
            scoring=self._build_scoring(scoring_payload, _FILE_SCORING),
        )

    def load_bundle(self, dataset_id: str) -> StrategyBundle:
        with self._lock:
            cached = self._bundle_cache.get(dataset_id)
            if cached is not None:
                return cached
            bundle = self._bundle_uncached(dataset_id)
            self._bundle_cache[dataset_id] = bundle
            self._hash_cache.pop(dataset_id, None)
            return bundle

    def strategy_hash(self, dataset_id: str) -> str:
        with self._lock:
            cached = self._hash_cache.get(dataset_id)
            if cached is not None:
                return cached
            bundle = self.load_bundle(dataset_id)
            canonical = json.dumps(
                bundle.model_dump(mode="json"),
                sort_keys=True,
                ensure_ascii=True,
                separators=(",", ":"),
            )
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            self._hash_cache[dataset_id] = digest
            return digest

    def get_digest(
        self,
        dataset_id: str,
        *,
        max_kpis: int = 10,
        max_rules: int = 8,
        max_pillars: int = 5,
    ) -> dict[str, Any]:
        bundle = self.load_bundle(dataset_id)
        north_star = bundle.targets.north_star

        pillars = []
        for pillar in bundle.targets.pillars[:max_pillars]:
            one_liner = pillar.description or (pillar.objectives[0] if pillar.objectives else "")
            pillars.append(
                {
                    "id": pillar.id,
                    "name": pillar.name,
                    "summary": _one_liner(one_liner, fallback=pillar.name),
                }
            )

        kpi_rows = []
        if bundle.kpis.north_star is not None:
            kpi_rows.append(bundle.kpis.north_star)
        kpi_rows.extend(bundle.kpis.kpis)
        top_kpis = []
        for item in kpi_rows[:max_kpis]:
            formula_hint = _one_liner(item.formula or item.logic, limit=90)
            top_kpis.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "summary": _one_liner(item.description, fallback=item.category or item.name),
                    "formula_hint": formula_hint or None,
                }
            )

        top_rules = []
        for item in bundle.rules.rules[:max_rules]:
            top_rules.append(
                {
                    "id": item.id,
                    "severity": item.severity,
                    "summary": _one_liner(item.description, fallback=item.name),
                }
            )

        weights = [
            {
                "name": item.name,
                "weight": item.weight,
            }
            for item in bundle.scoring.weights
        ]

        return {
            "north_star": {
                "id": north_star.id,
                "name": north_star.name,
                "description": _one_liner(north_star.description, fallback=north_star.name),
            },
            "pillars": pillars,
            "kpis": top_kpis,
            "rules": top_rules,
            "scoring_weights": weights,
        }


_STORE = StrategyStore()


def get_strategy_store() -> StrategyStore:
    return _STORE

