"""Run local API contract checks in one command."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

CONTRACT_SCRIPTS = [
    "contract_test_legacy_endpoints.py",
    "contract_test_dataset_endpoints.py",
    "contract_test_chart_data_shape.py",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all local API contract checks.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--dataset-id", default="silkroute", help="Dataset id")
    args = parser.parse_args()

    for script_name in CONTRACT_SCRIPTS:
        script_path = SCRIPT_DIR / script_name
        cmd = [
            sys.executable,
            str(script_path),
            "--base-url",
            args.base_url,
        ]
        if script_name != "contract_test_legacy_endpoints.py":
            cmd.extend(["--dataset-id", args.dataset_id])

        print(f"[INFO] Running {script_name} ...")
        completed = subprocess.run(cmd, cwd=SCRIPT_DIR.parent)
        if completed.returncode != 0:
            print(f"[ERROR] {script_name} failed with exit code {completed.returncode}.")
            return completed.returncode

    print("[OK] All API contract tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

