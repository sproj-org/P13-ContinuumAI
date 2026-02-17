"""Fail if legacy hardcoded mart identifiers/constants still exist in source code."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
SCAN_ROOTS = (BACKEND_DIR, FRONTEND_DIR)

TOKENS = (
    "mart_sales",
    "mart_customers",
    "mart_stores",
    "AVAILABLE_TABLES",
    "aggregationTables",
)
PATTERN = re.compile(r"\b(" + "|".join(re.escape(token) for token in TOKENS) + r")\b")
EXTRA_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "MARTS_SCHEMA = 'marts'",
        re.compile(r"""\bMARTS_SCHEMA\s*=\s*["']marts["']"""),
    ),
    (
        "FROM marts.",
        re.compile(r"""\bFROM\s+["']?marts["']?\.""", re.IGNORECASE),
    ),
]

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "node_modules",
    ".next",
    "__pycache__",
    "vendor",
}
EXCLUDED_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".docx",
    ".zip",
    ".pyc",
    ".pyd",
    ".dll",
    ".exe",
}
DOC_SUFFIXES = {".md", ".txt", ".rst"}
SELF_PATH = Path(__file__).resolve()


def _should_skip_path(path: Path) -> bool:
    if path.resolve() == SELF_PATH:
        return True
    if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if path.suffix.lower() in DOC_SUFFIXES:
        return True
    if path.as_posix().endswith("/backend/out/mart_sales_profile.json"):
        return True
    if path.as_posix().endswith("/backend/out/mart_customers_profile.json"):
        return True
    if path.as_posix().endswith("/backend/out/mart_stores_profile.json"):
        return True
    if "/backend/out/" in path.as_posix() and path.suffix.lower() == ".json":
        return True
    return False


def _iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _should_skip_path(path):
            continue
        yield path


def main() -> int:
    failures: list[str] = []

    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in _iter_files(root):
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            except OSError as exc:
                failures.append(f"{path}: failed to read file ({exc})")
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                match = PATTERN.search(line)
                if not match:
                    pass
                else:
                    if "mart_sales_profile.json" in line or "mart_customers_profile.json" in line or "mart_stores_profile.json" in line:
                        continue
                    failures.append(
                        f"{path}:{line_no}: found forbidden hardcoded token '{match.group(1)}'"
                    )

                for label, regex in EXTRA_PATTERNS:
                    if regex.search(line):
                        failures.append(
                            f"{path}:{line_no}: found forbidden pattern '{label}'"
                        )

    if failures:
        print("[ERROR] Hardcoded mart check failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("[OK] No forbidden hardcoded mart identifiers/constants found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
