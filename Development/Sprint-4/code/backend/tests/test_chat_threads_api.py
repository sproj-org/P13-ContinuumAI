from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

os.environ["DATABASE_URL"] = "sqlite:///./test_chat_threads_api.db"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.api.chat_threads import router as chat_threads_router
from app.core.security import get_current_user
from app.db.database import get_db


def _operational_error() -> OperationalError:
    return OperationalError(
        "SELECT 1",
        {},
        Exception("SSL SYSCALL error: EOF detected"),
    )


class _FakeThreadQuery:
    def __init__(self, db: "_BaseFakeDb") -> None:
        self._db = db

    def filter(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self

    def order_by(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self

    def all(self):  # type: ignore[no-untyped-def]
        return self._db.handle_all()

    def first(self):  # type: ignore[no-untyped-def]
        return self._db.handle_first()

    def delete(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self._db.handle_delete()


class _BaseFakeDb:
    def __init__(self) -> None:
        self.rollback_calls = 0
        self.invalidate_calls = 0
        self.added = []

    def query(self, model):  # type: ignore[no-untyped-def]
        return _FakeThreadQuery(self)

    def rollback(self) -> None:
        self.rollback_calls += 1

    def invalidate(self) -> None:
        self.invalidate_calls += 1

    def add(self, value) -> None:  # type: ignore[no-untyped-def]
        self.added.append(value)

    def handle_all(self):  # type: ignore[no-untyped-def]
        return []

    def handle_first(self):  # type: ignore[no-untyped-def]
        return None

    def handle_delete(self):  # type: ignore[no-untyped-def]
        return 0


class _RetryingListDb(_BaseFakeDb):
    def __init__(self) -> None:
        super().__init__()
        self._all_calls = 0

    def handle_all(self):  # type: ignore[no-untyped-def]
        self._all_calls += 1
        if self._all_calls == 1:
            raise _operational_error()
        return [
            SimpleNamespace(
                id=7,
                thread_key="silkroute:sales",
                turns=[{"role": "user", "message": "Show sales"}],
                chat_state=None,
                last_chart_spec=None,
                saved_prompts=[],
                chat_mode="chart",
                updated_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
            )
        ]


class _FailingListDb(_BaseFakeDb):
    def handle_all(self):  # type: ignore[no-untyped-def]
        raise _operational_error()


class _FailingWriteDb(_BaseFakeDb):
    def commit(self) -> None:
        raise _operational_error()

    def refresh(self, value) -> None:  # type: ignore[no-untyped-def]
        return None


def _build_client(db) -> TestClient:  # type: ignore[no-untyped-def]
    app = FastAPI()
    app.include_router(chat_threads_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_list_chat_threads_retries_once_and_recovers() -> None:
    client = _build_client(_RetryingListDb())

    response = client.get("/api/chat-threads")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["thread_key"] == "silkroute:sales"


def test_list_chat_threads_fails_soft_after_operational_error() -> None:
    db = _FailingListDb()
    client = _build_client(db)

    response = client.get("/api/chat-threads")

    assert response.status_code == 200
    assert response.json() == []
    assert db.rollback_calls >= 1
    assert db.invalidate_calls >= 1
    assert "traceback" not in response.text.lower()


def test_upsert_chat_thread_returns_clean_503_on_operational_error() -> None:
    db = _FailingWriteDb()
    client = _build_client(db)

    response = client.put(
        "/api/chat-threads",
        json={
            "thread_key": "silkroute:sales",
            "turns": [{"role": "user", "message": "Show sales"}],
            "chat_state": None,
            "last_chart_spec": None,
            "saved_prompts": [],
            "chat_mode": "chart",
        },
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["code"] == "chat_persistence_unavailable"
    assert payload["detail"]["message"] == "Chat persistence is temporarily unavailable."
    assert "traceback" not in json.dumps(payload).lower()
    assert db.rollback_calls >= 1
    assert db.invalidate_calls >= 1
