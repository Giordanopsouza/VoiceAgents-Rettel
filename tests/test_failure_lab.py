import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import init_db
from app.events import list_request_events, record_booking_attempt
from app.failure_lab import FailureLab
from app.main import create_app
from app.models import Appointment
from app.seed import seed_if_empty
from app.settings import Settings

BOOKING = {
    "call_id": "call_abc",
    "idempotency_key": "call_abc:booking",
    "slot_id": "SLOT-002",
    "patient_name": "Jordan Hale",
}
TIMEOUT_SECONDS = 0.05
DELAY_SECONDS = 0.25


def _engine(tmp_path: Path):
    db_engine = init_db(tmp_path / "calendar.sqlite")
    with Session(db_engine) as session:
        seed_if_empty(session)
    return db_engine


def _lab(*, enabled: bool) -> FailureLab:
    return FailureLab(
        timeout_seconds=TIMEOUT_SECONDS,
        delay_seconds=DELAY_SECONDS,
        enabled=enabled,
    )


def _client(tmp_path: Path, *, live_demo_enabled: bool = True):
    settings = Settings(
        database_path=tmp_path / "calendar.sqlite",
        live_demo_enabled=live_demo_enabled,
        retell_function_timeout_seconds=TIMEOUT_SECONDS,
        failure_lab_delay_seconds=DELAY_SECONDS,
        _env_file=None,
    )
    return TestClient(create_app(settings))


def _count_appointments(engine) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(Appointment)) or 0


def _wait_until_delayed_event(engine, timeout: float = 2.0) -> list[dict]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with Session(engine) as session:
            events = list_request_events(session)
        outcomes = [
            event["outcome"]
            for event in events
            if event["event_type"] == "response_outcome"
        ]
        if "created_then_response_delayed" in outcomes:
            return events
        time.sleep(0.01)
    raise AssertionError("delayed response event was not committed before the wait")


def test_operator_api_enables_and_disables_failure_mode(tmp_path: Path):
    with _client(tmp_path) as client:
        initial = client.get("/api/failure-lab")
        enabled = client.put("/api/failure-lab", json={"enabled": True})
        after_enable = client.get("/api/failure-lab")
        disabled = client.put("/api/failure-lab", json={"enabled": False})

    assert initial.status_code == 200
    assert initial.json() == {
        "enabled": False,
        "timeout_seconds": TIMEOUT_SECONDS,
        "delay_seconds": DELAY_SECONDS,
    }
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    assert after_enable.json()["enabled"] is True
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False


def test_normal_mode_responds_without_artificial_delay(tmp_path: Path):
    engine = _engine(tmp_path)
    lab = _lab(enabled=False)

    started = time.monotonic()
    with Session(engine) as session:
        result = record_booking_attempt(session, failure_lab=lab, **BOOKING)
        events = list_request_events(session)
    elapsed = time.monotonic() - started
    engine.dispose()

    assert result["replayed"] is False
    assert elapsed < DELAY_SECONDS / 2
    assert [event["outcome"] for event in events][-1] == "created_returned"


def test_failure_mode_commits_before_delaying_the_first_response(tmp_path: Path):
    engine = _engine(tmp_path)
    lab = _lab(enabled=True)

    def first_attempt():
        with Session(engine) as session:
            return record_booking_attempt(session, failure_lab=lab, **BOOKING)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(first_attempt)
        events = _wait_until_delayed_event(engine)
        still_waiting = not future.done()
        result = future.result(timeout=2)

    engine.dispose()

    assert still_waiting is True
    assert result["replayed"] is False
    assert result["appointment"]["id"] == "APT-001"
    assert events[-1]["outcome"] == "created_then_response_delayed"


def test_only_the_first_attempt_for_a_key_is_delayed(tmp_path: Path):
    engine = _engine(tmp_path)
    lab = _lab(enabled=True)

    with Session(engine) as session:
        first = record_booking_attempt(session, failure_lab=lab, **BOOKING)
    started = time.monotonic()
    with Session(engine) as session:
        second = record_booking_attempt(session, failure_lab=lab, **BOOKING)
        events = list_request_events(session)
    retry_elapsed = time.monotonic() - started
    engine.dispose()

    assert first["replayed"] is False
    assert second["replayed"] is True
    assert retry_elapsed < DELAY_SECONDS / 2
    outcomes = [event["outcome"] for event in events if event["event_type"] == "response_outcome"]
    assert outcomes == ["created_then_response_delayed", "duplicate_returned"]


def test_concurrent_retry_returns_existing_id_without_waiting(tmp_path: Path):
    engine = _engine(tmp_path)
    lab = _lab(enabled=True)

    def attempt():
        with Session(engine) as session:
            return record_booking_attempt(session, failure_lab=lab, **BOOKING)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(attempt)
        _wait_until_delayed_event(engine)
        started = time.monotonic()
        second = attempt()
        retry_elapsed = time.monotonic() - started
        first = first_future.result(timeout=2)
        appointment_count = _count_appointments(engine)
        with Session(engine) as session:
            events = list_request_events(session)

    engine.dispose()

    assert first["appointment"]["id"] == second["appointment"]["id"] == "APT-001"
    assert first["replayed"] is False
    assert second["replayed"] is True
    assert retry_elapsed < DELAY_SECONDS / 2
    assert appointment_count == 1
    outcomes = [event["outcome"] for event in events if event["event_type"] == "response_outcome"]
    assert outcomes == ["created_then_response_delayed", "duplicate_returned"]


def test_reset_allows_failure_lab_to_delay_the_next_first_attempt(tmp_path: Path):
    with _client(tmp_path) as client:
        enable = client.put("/api/failure-lab", json={"enabled": True})
        lab: FailureLab = client.app.state.failure_lab
        with client.app.state.session_factory() as session:
            record_booking_attempt(session, failure_lab=lab, **BOOKING)
        claimed_again_before_reset = lab.claim_delay(BOOKING["idempotency_key"])
        reset = client.post("/api/demo/reset")
        claimed_after_reset = lab.claim_delay(BOOKING["idempotency_key"])

    assert enable.status_code == 200
    assert claimed_again_before_reset is False
    assert reset.status_code == 200
    assert claimed_after_reset is True
