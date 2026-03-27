"""File-backed state store for minimal alerting."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AlertStateStore:
    """Persist last-seen signal severities per dataset in a JSON file."""

    def __init__(self, file_path: str) -> None:
        self._path = Path(file_path)

    def load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"datasets": {}}

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"datasets": {}}

        if not isinstance(payload, dict):
            return {"datasets": {}}

        datasets = payload.get("datasets")
        if not isinstance(datasets, dict):
            payload["datasets"] = {}
        return payload

    def save(self, payload: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        rendered = json.dumps(payload, indent=2, ensure_ascii=True)
        self._path.write_text(rendered + "\n", encoding="utf-8")

    def get_dataset_state(self, dataset_id: str) -> dict[str, Any]:
        payload = self.load()
        datasets = payload.get("datasets", {})
        if not isinstance(datasets, dict):
            return {}
        state = datasets.get(dataset_id)
        return state if isinstance(state, dict) else {}

    def update_dataset_state(
        self,
        *,
        dataset_id: str,
        revision: str | None,
        generated_at: str | None,
        severity_by_signal: dict[str, str],
    ) -> None:
        payload = self.load()
        datasets = payload.get("datasets")
        if not isinstance(datasets, dict):
            datasets = {}
            payload["datasets"] = datasets

        datasets[dataset_id] = {
            "revision": revision,
            "generated_at": generated_at,
            "last_run_at": datetime.now(timezone.utc).isoformat(),
            "severity_by_signal": severity_by_signal,
        }
        self.save(payload)
