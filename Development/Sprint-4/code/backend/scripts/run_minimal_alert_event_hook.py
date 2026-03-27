"""Event-hook runner: execute alert check after strategy recompute completes."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _append_monitor_log(*, path: Path, entry: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def main() -> int:
    os.chdir(BACKEND_ROOT)
    os.environ.setdefault("JWT_SECRET_KEY", "alerts-local-secret")

    parser = argparse.ArgumentParser(
        description="Run minimal alert check as a post-recompute event hook.",
    )
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument(
        "--source",
        default="strategy_recompute",
        help="Caller/source tag (pipeline, api, job name).",
    )
    parser.add_argument(
        "--monitor-log",
        default="out/alerts_monitor.jsonl",
        help="JSONL monitor log destination.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from app.db.database import SessionLocal
    from app.services.alerts_minimal.checker import run_alert_check

    db = SessionLocal()
    try:
        result = run_alert_check(
            dataset_id=args.dataset_id,
            db=db,
            dry_run=args.dry_run,
            force=False,
            update_state_in_dry_run=False,
        )
    finally:
        db.close()

    payload = {
        "dataset_id": result.dataset_id,
        "alert_triggered": result.alert_triggered,
        "email_sent": result.email_sent,
        "dry_run": result.dry_run,
        "reason": result.reason,
        "transition_count": result.transition_count,
        "revision": result.revision,
        "generated_at": result.generated_at,
    }

    monitor_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": args.source,
        **payload,
    }
    _append_monitor_log(path=Path(args.monitor_log), entry=monitor_entry)

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
