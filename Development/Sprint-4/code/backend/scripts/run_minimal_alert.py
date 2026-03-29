"""Run minimal KPI escalation email alert checks for a dataset."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> int:
    os.chdir(BACKEND_ROOT)
    os.environ.setdefault("JWT_SECRET_KEY", "alerts-local-secret")

    parser = argparse.ArgumentParser(description="Run minimal KPI escalation alerts.")
    parser.add_argument("--dataset-id", required=True, help="Dataset id to evaluate")
    parser.add_argument("--dry-run", action="store_true", help="Compute alerts but do not send email")
    parser.add_argument("--force", action="store_true", help="Trigger alert even without new critical transition")
    parser.add_argument(
        "--update-state-in-dry-run",
        action="store_true",
        help="Persist current severities even when --dry-run is set",
    )
    args = parser.parse_args()

    from app.db.database import SessionLocal
    from app.services.alerts_minimal.checker import run_alert_check

    db = SessionLocal()
    try:
        result = run_alert_check(
            dataset_id=args.dataset_id,
            db=db,
            dry_run=args.dry_run,
            force=args.force,
            update_state_in_dry_run=args.update_state_in_dry_run,
        )
    finally:
        db.close()

    print(
        json.dumps(
            {
                "dataset_id": result.dataset_id,
                "alert_triggered": result.alert_triggered,
                "email_sent": result.email_sent,
                "dry_run": result.dry_run,
                "reason": result.reason,
                "transition_count": result.transition_count,
                "revision": result.revision,
                "generated_at": result.generated_at,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
