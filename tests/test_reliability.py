from pathlib import Path

from fastapi.testclient import TestClient

from app.events import record_booking_attempt
from app.main import create_app
from app.reliability import (
    DUPLICATE_PREVENTED,
    SINGLE_BOOKED,
    dashboard_evidence,
    shorten_idempotency_key,
)
from app.settings import Settings

LONG_KEY = "bk_be163e9b6c7e833f09eb13223e2f0edb0f256169963ea630ba75cf873bd732d0"


def _event(**overrides) -> dict:
    event = {
        "id": 1,
        "created_at": "2026-09-10T12:00:00Z",
        "attempt_number": 1,
        "event_type": "receipt",
        "outcome": "received",
        "appointment_id": None,
        "idempotency_key": LONG_KEY,
        "call_id": "call_abc",
    }
    event.update(overrides)
    return event


def _booking_attempt(
    *,
    attempt_number: int,
    created_at: str,
    decision: str,
    appointment_outcome: str,
    response_outcome: str,
    start_id: int,
) -> list[dict]:
    appointment_id = "APT-001" if appointment_outcome != "rejected" else None
    followup_id = appointment_id
    return [
        _event(
            id=start_id,
            created_at=created_at,
            attempt_number=attempt_number,
            event_type="receipt",
            outcome="received",
            appointment_id=None,
        ),
        _event(
            id=start_id + 1,
            created_at=created_at,
            attempt_number=attempt_number,
            event_type="idempotency_decision",
            outcome=decision,
            appointment_id=followup_id,
        ),
        _event(
            id=start_id + 2,
            created_at=created_at,
            attempt_number=attempt_number,
            event_type="appointment_result",
            outcome=appointment_outcome,
            appointment_id=followup_id,
        ),
        _event(
            id=start_id + 3,
            created_at=created_at,
            attempt_number=attempt_number,
            event_type="response_outcome",
            outcome=response_outcome,
            appointment_id=followup_id,
        ),
    ]


def _client(tmp_path: Path, *, live_demo_enabled: bool = True):
    settings = Settings(
        database_path=tmp_path / "calendar.sqlite",
        live_demo_enabled=live_demo_enabled,
        _env_file=None,
    )
    return TestClient(create_app(settings))


def test_empty_events_do_not_claim_success():
    payload = dashboard_evidence([])

    assert payload["attempts"] == []
    assert payload["reliability"] == {"state": "empty", "headline": None}
    assert DUPLICATE_PREVENTED not in str(payload)


def test_duplicate_prevented_requires_two_attempts_one_appointment():
    events = [
        *_booking_attempt(
            attempt_number=1,
            created_at="2026-09-10T12:00:00Z",
            decision="new_key",
            appointment_outcome="created",
            response_outcome="created_then_response_delayed",
            start_id=1,
        ),
        *_booking_attempt(
            attempt_number=2,
            created_at="2026-09-10T12:00:03Z",
            decision="existing_key",
            appointment_outcome="replayed",
            response_outcome="duplicate_returned",
            start_id=5,
        ),
    ]

    payload = dashboard_evidence(events)
    reliability = payload["reliability"]
    attempts = payload["attempts"]

    assert reliability == {
        "state": "duplicate_prevented",
        "headline": DUPLICATE_PREVENTED,
    }
    assert [attempt["attempt_number"] for attempt in attempts] == [1, 2]
    assert [attempt["relative_s"] for attempt in attempts] == [0, 3]
    assert [attempt["outcome"] for attempt in attempts] == [
        "created_then_response_delayed",
        "duplicate_returned",
    ]
    assert {attempt["appointment_id"] for attempt in attempts} == {"APT-001"}
    assert {attempt["idempotency_key_short"] for attempt in attempts} == {
        "bk_be163…d732d0"
    }


def test_single_successful_booking_uses_a_different_result():
    events = _booking_attempt(
        attempt_number=1,
        created_at="2026-09-10T12:00:00Z",
        decision="new_key",
        appointment_outcome="created",
        response_outcome="created_returned",
        start_id=1,
    )

    payload = dashboard_evidence(events)

    assert payload["reliability"] == {"state": "booked", "headline": SINGLE_BOOKED}
    assert payload["reliability"]["headline"] != DUPLICATE_PREVENTED


def test_delayed_first_attempt_without_retry_is_incomplete():
    events = _booking_attempt(
        attempt_number=1,
        created_at="2026-09-10T12:00:00Z",
        decision="new_key",
        appointment_outcome="created",
        response_outcome="created_then_response_delayed",
        start_id=1,
    )

    payload = dashboard_evidence(events)

    assert payload["reliability"] == {"state": "incomplete", "headline": None}
    assert DUPLICATE_PREVENTED not in str(payload["reliability"])
    assert SINGLE_BOOKED not in str(payload["reliability"])


def test_rejected_booking_never_claims_success():
    events = _booking_attempt(
        attempt_number=1,
        created_at="2026-09-10T12:00:00Z",
        decision="new_key",
        appointment_outcome="rejected",
        response_outcome="slot_rejected",
        start_id=1,
    )

    payload = dashboard_evidence(events)

    assert payload["reliability"] == {"state": "failed", "headline": None}
    assert DUPLICATE_PREVENTED not in str(payload)
    assert SINGLE_BOOKED not in str(payload)


def test_two_appointments_never_claim_duplicate_prevented():
    first = _booking_attempt(
        attempt_number=1,
        created_at="2026-09-10T12:00:00Z",
        decision="new_key",
        appointment_outcome="created",
        response_outcome="created_returned",
        start_id=1,
    )
    second = _booking_attempt(
        attempt_number=1,
        created_at="2026-09-10T12:00:04Z",
        decision="new_key",
        appointment_outcome="created",
        response_outcome="created_returned",
        start_id=5,
    )
    for event in second:
        event["idempotency_key"] = "bk_other"
        if event["appointment_id"] == "APT-001":
            event["appointment_id"] = "APT-002"

    payload = dashboard_evidence(first + second)

    assert payload["reliability"]["state"] == "failed"
    assert payload["reliability"]["headline"] is None
    assert DUPLICATE_PREVENTED not in str(payload["reliability"])


def test_shortened_key_keeps_prefix_and_suffix():
    assert shorten_idempotency_key(LONG_KEY) == "bk_be163…d732d0"
    assert shorten_idempotency_key("short-key") == "short-key"
    assert shorten_idempotency_key(None) is None


def test_availability_attempts_do_not_create_a_booking_result():
    events = [
        _event(
            id=1,
            idempotency_key=None,
            event_type="receipt",
            outcome="received",
        ),
        _event(
            id=2,
            idempotency_key=None,
            event_type="availability_result",
            outcome="slots_returned",
        ),
        _event(
            id=3,
            idempotency_key=None,
            event_type="response_outcome",
            outcome="returned",
        ),
    ]

    payload = dashboard_evidence(events)

    assert payload["attempts"] == [
        {
            "attempt_number": 1,
            "kind": "availability",
            "relative_s": 0,
            "outcome": "returned",
            "complete": True,
            "idempotency_key": None,
            "idempotency_key_short": None,
            "appointment_id": None,
        }
    ]
    assert payload["reliability"] == {"state": "empty", "headline": None}


def test_events_api_includes_attempts_and_reliability(tmp_path: Path):
    with _client(tmp_path) as client:
        empty = client.get("/api/events")
        with client.app.state.session_factory() as session:
            record_booking_attempt(
                session,
                call_id="call_abc",
                idempotency_key=LONG_KEY,
                slot_id="SLOT-002",
                patient_name="Jordan Hale",
            )
            record_booking_attempt(
                session,
                call_id="call_abc",
                idempotency_key=LONG_KEY,
                slot_id="SLOT-002",
                patient_name="Jordan Hale",
            )
        populated = client.get("/api/events")

    assert empty.status_code == 200
    assert empty.json()["events"] == []
    assert empty.json()["attempts"] == []
    assert empty.json()["reliability"] == {"state": "empty", "headline": None}

    body = populated.json()
    assert populated.status_code == 200
    assert body["reliability"] == {
        "state": "duplicate_prevented",
        "headline": DUPLICATE_PREVENTED,
    }
    assert [attempt["attempt_number"] for attempt in body["attempts"]] == [1, 2]
    assert body["attempts"][0]["idempotency_key_short"] == "bk_be163…d732d0"
    assert {attempt["appointment_id"] for attempt in body["attempts"]} == {"APT-001"}


def test_events_api_marks_a_normal_booking_without_the_retry_claim(tmp_path: Path):
    with _client(tmp_path) as client:
        with client.app.state.session_factory() as session:
            record_booking_attempt(
                session,
                call_id="call_abc",
                idempotency_key=LONG_KEY,
                slot_id="SLOT-002",
                patient_name="Jordan Hale",
            )
        response = client.get("/api/events")

    body = response.json()
    assert body["reliability"] == {"state": "booked", "headline": SINGLE_BOOKED}
    assert body["attempts"][0]["outcome"] == "created_returned"
