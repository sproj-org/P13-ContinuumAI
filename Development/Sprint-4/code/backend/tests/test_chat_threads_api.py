from __future__ import annotations

import json
import os
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.exc import DetachedInstanceError

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


class _DetachingUser:
    def __init__(self, user_id: int) -> None:
        self._user_id = user_id
        self._detached = False

    @property
    def id(self) -> int:
        if self._detached:
            raise DetachedInstanceError("User instance is detached")
        return self._user_id

    def detach(self) -> None:
        self._detached = True


class _FailingListDbThatDetachesUser(_FailingListDb):
    def __init__(self, user: _DetachingUser) -> None:
        super().__init__()
        self._user = user

    def invalidate(self) -> None:
        super().invalidate()
        self._user.detach()


def test_list_chat_threads_fails_soft_after_operational_error() -> None:
    db = _FailingListDb()
    client = _build_client(db)

    response = client.get("/api/chat-threads")

    assert response.status_code == 200
    assert response.json() == []
    assert db.rollback_calls >= 1
    assert db.invalidate_calls >= 1
    assert "traceback" not in response.text.lower()


def test_list_chat_threads_survives_user_detach_after_invalidation() -> None:
    detaching_user = _DetachingUser(user_id=42)
    db = _FailingListDbThatDetachesUser(detaching_user)
    app = FastAPI()
    app.include_router(chat_threads_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: detaching_user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.get("/api/chat-threads")

    assert response.status_code == 200
    assert response.json() == []
    assert db.invalidate_calls >= 1
    assert "DetachedInstanceError" not in response.text


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
