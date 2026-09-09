from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.availability import AvailabilityQueryError
from app.booking import BookingError
from app.db import init_db
from app.events import (
    list_request_events,
    record_availability_attempt,
    record_booking_attempt,
)
from app.main import create_app
from app.seed import reset_calendar, seed_if_empty
from app.settings import Settings

BOOKING_EVENT_TYPES = [
    "receipt",
    "idempotency_decision",
    "appointment_result",
    "response_outcome",
]
AVAILABILITY_EVENT_TYPES = [
    "receipt",
    "availability_result",
    "response_outcome",
]
PUBLIC_EVENT_KEYS = {
    "id",
    "created_at",
    "attempt_number",
    "event_type",
    "outcome",
    "appointment_id",
    "idempotency_key",
    "call_id",
}
FORBIDDEN_KEYS = {
    "api_key",
    "retell_api_key",
    "signature",
    "x-retell-signature",
    "access_token",
    "token",
    "transcript",
    "phone",
    "email",
    "patient_name",
    "authorization",
}


def _client(tmp_path: Path, *, live_demo_enabled: bool = False):
    settings = Settings(
        database_path=tmp_path / "calendar.sqlite",
        live_demo_enabled=live_demo_enabled,
        _env_file=None,
    )
    return TestClient(create_app(settings))


def _event_types(events: list[dict]) -> list[str]:
    return [event["event_type"] for event in events]


def _assert_sanitized(payload: object) -> None:
    if isinstance(payload, dict):
        assert FORBIDDEN_KEYS.isdisjoint(payload.keys())
        for value in payload.values():
            _assert_sanitized(value)
    elif isinstance(payload, list):
        for item in payload:
            _assert_sanitized(item)


def test_booking_attempt_records_receipt_decision_result_and_outcome(tmp_path: Path):
    engine = init_db(tmp_path / "calendar.sqlite")
    with Session(engine) as session:
        seed_if_empty(session)
        result = record_booking_attempt(
            session,
            call_id="call_abc",
            idempotency_key="call_abc:booking",
            slot_id="SLOT-002",
            patient_name="Jordan Hale",
        )
        events = list_request_events(session)
    engine.dispose()

    assert result["replayed"] is False
    assert result["appointment"]["id"] == "APT-001"
    assert _event_types(events) == BOOKING_EVENT_TYPES
    assert [event["attempt_number"] for event in events] == [1, 1, 1, 1]
    assert [event["outcome"] for event in events] == [
        "received",
        "new_key",
        "created",
        "created_returned",
    ]
    assert events[0]["appointment_id"] is None
    assert {event["appointment_id"] for event in events[1:]} == {"APT-001"}


def test_retry_events_correlate_by_call_id_and_idempotency_key(tmp_path: Path):
    engine = init_db(tmp_path / "calendar.sqlite")
    with Session(engine) as session:
        seed_if_empty(session)
        first = record_booking_attempt(
            session,
            call_id="call_abc",
            idempotency_key="call_abc:booking",
            slot_id="SLOT-002",
            patient_name="Jordan Hale",
        )
        second = record_booking_attempt(
            session,
            call_id="call_abc",
            idempotency_key="call_abc:booking",
            slot_id="SLOT-002",
            patient_name="Jordan Hale",
        )
        events = list_request_events(session)
    engine.dispose()

    assert first["appointment"]["id"] == second["appointment"]["id"] == "APT-001"
    assert second["replayed"] is True
    assert len(events) == 8
    assert {event["call_id"] for event in events} == {"call_abc"}
    assert {event["idempotency_key"] for event in events} == {"call_abc:booking"}
    assert [event["attempt_number"] for event in events[:4]] == [1, 1, 1, 1]
    assert [event["attempt_number"] for event in events[4:]] == [2, 2, 2, 2]
    assert _event_types(events[4:]) == BOOKING_EVENT_TYPES
    assert [event["outcome"] for event in events[4:]] == [
        "received",
        "existing_key",
        "replayed",
        "duplicate_returned",
    ]
    assert {event["appointment_id"] for event in events[5:]} == {"APT-001"}


def test_event_payloads_omit_secrets_and_personal_details(tmp_path: Path):
    with _client(tmp_path) as client:
        with client.app.state.session_factory() as session:
            record_booking_attempt(
                session,
                call_id="x-retell-signature",
                idempotency_key="call_abc:booking",
                slot_id="SLOT-002",
                patient_name="Jordan Hale",
            )
        response = client.get("/api/events")

    body = response.json()
    assert response.status_code == 200
    events = body["events"]
    assert events
    assert all(set(event) == PUBLIC_EVENT_KEYS for event in events)
    _assert_sanitized(body)
    assert "x-retell-signature" not in response.text
    assert "Jordan Hale" not in response.text
    assert "sk-" not in response.text.lower()
    assert "transcript" not in response.text.lower()


def test_events_are_returned_in_chronological_order(tmp_path: Path):
    engine = init_db(tmp_path / "calendar.sqlite")
    with Session(engine) as session:
        seed_if_empty(session)
        record_availability_attempt(
            session, call_id="call_abc", query_date="2026-09-14"
        )
        record_booking_attempt(
            session,
            call_id="call_abc",
            idempotency_key="call_abc:booking",
            slot_id="SLOT-002",
            patient_name="Jordan Hale",
        )
        record_booking_attempt(
            session,
            call_id="call_def",
            idempotency_key="call_def:booking",
            slot_id="SLOT-003",
            patient_name="Sam Rivera",
        )
        events = list_request_events(session)
    engine.dispose()

    assert events == sorted(events, key=lambda event: (event["created_at"], event["id"]))
    assert [event["id"] for event in events] == list(range(1, len(events) + 1))
    assert events[0]["event_type"] == "receipt"
    assert events[0]["call_id"] == "call_abc"
    assert events[-1]["call_id"] == "call_def"
    assert events[-1]["outcome"] == "created_returned"


def test_read_api_returns_current_demo_session(tmp_path: Path):
    with _client(tmp_path, live_demo_enabled=True) as client:
        empty = client.get("/api/events")
        with client.app.state.session_factory() as session:
            record_booking_attempt(
                session,
                call_id="call_abc",
                idempotency_key="call_abc:booking",
                slot_id="SLOT-002",
                patient_name="Jordan Hale",
            )
        populated = client.get("/api/events")
        reset = client.post("/api/demo/reset")
        after_reset = client.get("/api/events")

    assert empty.status_code == 200
    assert empty.json() == {"events": []}
    assert populated.status_code == 200
    events = populated.json()["events"]
    assert _event_types(events) == BOOKING_EVENT_TYPES
    assert {event["call_id"] for event in events} == {"call_abc"}
    assert {event["idempotency_key"] for event in events} == {"call_abc:booking"}
    assert reset.status_code == 200
    assert after_reset.status_code == 200
    assert after_reset.json() == {"events": []}


def test_read_api_stays_available_when_live_demo_is_paused(tmp_path: Path):
    with _client(tmp_path, live_demo_enabled=False) as client:
        with client.app.state.session_factory() as session:
            record_booking_attempt(
                session,
                call_id="call_abc",
                idempotency_key="call_abc:booking",
                slot_id="SLOT-002",
                patient_name="Jordan Hale",
            )
        response = client.get("/api/events")

    assert response.status_code == 200
    assert _event_types(response.json()["events"]) == BOOKING_EVENT_TYPES


def test_availability_attempt_records_timeline_events(tmp_path: Path):
    engine = init_db(tmp_path / "calendar.sqlite")
    with Session(engine) as session:
        seed_if_empty(session)
        result = record_availability_attempt(
            session, call_id="call_abc", query_date="2026-09-14"
        )
        events = list_request_events(session)
        with pytest.raises(AvailabilityQueryError):
            record_availability_attempt(
                session, call_id="call_abc", query_date="next Tuesday"
            )
        after_error = list_request_events(session)
    engine.dispose()

    assert result["date"] == "2026-09-14"
    assert _event_types(events) == AVAILABILITY_EVENT_TYPES
    assert [event["attempt_number"] for event in events] == [1, 1, 1]
    assert [event["outcome"] for event in events] == [
        "received",
        "slots_returned",
        "returned",
    ]
    assert {event["call_id"] for event in events} == {"call_abc"}
    assert {event["idempotency_key"] for event in events} == {None}
    assert _event_types(after_error[3:]) == AVAILABILITY_EVENT_TYPES
    assert [event["attempt_number"] for event in after_error[3:]] == [2, 2, 2]
    assert after_error[-2]["outcome"] == "invalid_date"


def test_availability_http_does_not_write_timeline_events(tmp_path: Path):
    with _client(tmp_path) as client:
        lookup = client.get("/api/availability", params={"date": "2026-09-14"})
        events = client.get("/api/events")

    assert lookup.status_code == 200
    assert events.json() == {"events": []}


def test_failed_booking_still_records_all_four_event_types(tmp_path: Path):
    engine = init_db(tmp_path / "calendar.sqlite")
    with Session(engine) as session:
        seed_if_empty(session)
        with pytest.raises(BookingError) as unknown:
            record_booking_attempt(
                session,
                call_id="call_abc",
                idempotency_key="call_abc:booking",
                slot_id="SLOT-999",
                patient_name="Jordan Hale",
            )
        record_booking_attempt(
            session,
            call_id="call_abc",
            idempotency_key="call_abc:booking",
            slot_id="SLOT-002",
            patient_name="Jordan Hale",
        )
        with pytest.raises(BookingError) as conflict:
            record_booking_attempt(
                session,
                call_id="call_abc",
                idempotency_key="call_abc:booking",
                slot_id="SLOT-003",
                patient_name="Sam Rivera",
            )
        events = list_request_events(session)
    engine.dispose()

    assert unknown.value.error == "unknown_slot"
    assert conflict.value.error == "idempotency_conflict"
    unknown_events = events[:4]
    conflict_events = events[-4:]
    assert _event_types(unknown_events) == BOOKING_EVENT_TYPES
    assert [event["outcome"] for event in unknown_events] == [
        "received",
        "new_key",
        "rejected",
        "slot_rejected",
    ]
    assert _event_types(conflict_events) == BOOKING_EVENT_TYPES
    assert [event["outcome"] for event in conflict_events] == [
        "received",
        "conflict",
        "rejected",
        "conflict_returned",
    ]
    assert {event["call_id"] for event in events} == {"call_abc"}
    assert {event["idempotency_key"] for event in events} == {"call_abc:booking"}


def test_reset_clears_events_from_the_read_api(tmp_path: Path):
    engine = init_db(tmp_path / "calendar.sqlite")
    with Session(engine) as session:
        seed_if_empty(session)
        record_booking_attempt(
            session,
            call_id="call_abc",
            idempotency_key="call_abc:booking",
            slot_id="SLOT-002",
            patient_name="Jordan Hale",
        )
        reset_calendar(session)
        events = list_request_events(session)
    engine.dispose()

    assert events == []
