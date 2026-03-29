from __future__ import annotations

from types import SimpleNamespace

from app.services.alerts_minimal.checker import detect_critical_transitions, run_alert_check
from app.services.alerts_minimal.state_store import AlertStateStore


def _settings(tmp_path, *, enabled: bool = True, recipients: str = "alerts@example.com") -> SimpleNamespace:
    return SimpleNamespace(
        ALERTS_ENABLED=enabled,
        ALERT_STATE_FILE=str(tmp_path / "alerts_state.json"),
        ALERT_EMAIL_TO=recipients,
        ALERT_EMAIL_FROM="noreply@example.com",
        SMTP_HOST="smtp.example.com",
        SMTP_PORT=587,
        SMTP_USER="user",
        SMTP_PASSWORD="pass",
        SMTP_USE_TLS=True,
    )


def test_detect_critical_transitions_only_new_or_escalated() -> None:
    previous = {"s1": "warn", "s2": "critical", "s3": "ok"}
    current = [
        {"id": "s1", "severity": "critical", "title": "one"},
        {"id": "s2", "severity": "critical", "title": "two"},
        {"id": "s3", "severity": "warn", "title": "three"},
        {"id": "s4", "severity": "critical", "title": "four"},
    ]

    transitions = detect_critical_transitions(previous, current)
    transition_ids = {item["id"] for item in transitions}
    assert transition_ids == {"s1", "s4"}


def test_run_alert_check_no_escalation_updates_state(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    settings = _settings(tmp_path)

    monkeypatch.setattr(
        "app.services.alerts_minimal.checker.build_decision_surface",
        lambda dataset_id, db: {
            "dataset_id": dataset_id,
            "revision": "r1",
            "generated_at": "2026-03-07T00:00:00Z",
            "decision_signals": [{"id": "margin", "severity": "warn", "title": "Margin pressure"}],
        },
    )

    result = run_alert_check(dataset_id="silkroute", db=object(), dry_run=True, settings=settings)

    assert result.alert_triggered is False
    assert result.reason == "no_escalation"

    store = AlertStateStore(settings.ALERT_STATE_FILE)
    state = store.get_dataset_state("silkroute")
    assert state["severity_by_signal"]["margin"] == "warn"


def test_run_alert_check_critical_transition_dry_run_no_state_write(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    settings = _settings(tmp_path)

    store = AlertStateStore(settings.ALERT_STATE_FILE)
    store.update_dataset_state(
        dataset_id="silkroute",
        revision="r0",
        generated_at="2026-03-06T00:00:00Z",
        severity_by_signal={"margin": "warn"},
    )

    monkeypatch.setattr(
        "app.services.alerts_minimal.checker.build_decision_surface",
        lambda dataset_id, db: {
            "dataset_id": dataset_id,
            "revision": "r2",
            "generated_at": "2026-03-08T00:00:00Z",
            "decision_signals": [
                {
                    "id": "margin",
                    "severity": "critical",
                    "title": "Margin at risk",
                    "explanation": "Steep drop",
                    "suggested_action": "Revisit discounting",
                }
            ],
        },
    )

    result = run_alert_check(dataset_id="silkroute", db=object(), dry_run=True, settings=settings)

    assert result.alert_triggered is True
    assert result.email_sent is False
    assert result.reason == "critical_transition"
    assert result.transition_count == 1

    # State remains unchanged in dry run unless update_state_in_dry_run=True.
    state_after = store.get_dataset_state("silkroute")
    assert state_after["severity_by_signal"]["margin"] == "warn"
