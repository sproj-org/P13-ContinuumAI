"""Minimal strategy-layer smoke test for silkroute."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())


def main() -> int:
    os.chdir(BACKEND_ROOT)
    os.environ.setdefault("JWT_SECRET_KEY", "strategy-smoke-local-secret")

    parser = argparse.ArgumentParser(description="Run strategy layer smoke checks.")
    parser.add_argument("--dataset-id", default="silkroute")
    args = parser.parse_args()
    dataset_id = args.dataset_id

    from app.core.config import get_settings
    from app.services.agents.chat_orchestrator import _build_system_prompt, _load_strategy_runtime, run_chat_orchestration
    from app.services.strategy.store import get_strategy_store

    print(f"[SMOKE] dataset={dataset_id}")

    store = get_strategy_store()
    bundle = store.load_bundle(dataset_id)
    strategy_hash = store.strategy_hash(dataset_id)
    digest = store.get_digest(dataset_id)

    north_star = digest.get("north_star", {}).get("name")
    if not isinstance(north_star, str) or not north_star.strip():
        print("[FAIL] north star missing in digest")
        return 1

    print(f"[OK] north_star={north_star}")
    print(f"[OK] strategy_hash={strategy_hash}")
    print(f"[OK] pillars={len(digest.get('pillars', []))} kpis={len(digest.get('kpis', []))} rules={len(digest.get('rules', []))}")

    strategy_digest, _, strategy_notice = _load_strategy_runtime(dataset_id)
    prompt = _build_system_prompt("explain", strategy_digest=strategy_digest, strategy_notice=strategy_notice)
    if "STRATEGY LAYER" not in prompt:
        print("[FAIL] system prompt missing STRATEGY LAYER section")
        return 1
    if north_star not in prompt:
        print("[FAIL] system prompt missing north star name")
        return 1
    print("[OK] system prompt includes strategy layer and north star")

    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        print("[SKIP] OPENAI_API_KEY missing; skipping optional live explain call")
        return 0

    try:
        from app.db.database import SessionLocal

        db = SessionLocal()
        try:
            payload = run_chat_orchestration(
                dataset_id=dataset_id,
                message="Explain our north star KPI and which pillars support it",
                table="gold_sales_daily",
                mode="explain",
                state=None,
                history=None,
                db=db,
                debug=False,
            )
        finally:
            db.close()
    except Exception as exc:  # pragma: no cover - depends on env/runtime services
        print(f"[SKIP] optional live explain call unavailable: {exc}")
        return 0

    response_type = payload.get("response_type")
    message = str(payload.get("message", ""))
    if response_type != "explain":
        print(f"[FAIL] optional live explain expected response_type=explain, got {response_type}")
        return 1
    if _normalize(north_star) not in _normalize(message):
        print("[FAIL] optional live explain message did not mention north star")
        return 1

    print("[OK] optional live explain call returned strategy-aligned explain response")
    _ = bundle
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
