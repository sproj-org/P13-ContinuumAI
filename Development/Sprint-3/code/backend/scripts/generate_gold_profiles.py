"""Generate validated gold profiles in backend/out/gold_*_profile.json."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from services.profiling.gold_profile_generator import generate_gold_profiles


def main() -> int:
    if not os.getenv("DATABASE_URL"):
        print("[ERROR] DATABASE_URL environment variable is required.")
        return 1

    try:
        written = generate_gold_profiles()
    except Exception as exc:
        print(f"[ERROR] Gold profile generation failed: {exc}")
        traceback.print_exc()
        return 1

    for path in written:
        print(f"[OK] wrote {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
