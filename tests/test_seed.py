from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import init_db
from app.main import create_app
from app.models import Appointment, AppointmentSlot, IdempotencyRecord, RequestEvent
from app.seed import reset_calendar, seed_if_empty
from app.settings import Settings

DENTIST = "Dr. Elena Voss"
DEMO_DATES = ["2026-09-14", "2026-09-15"]
EXPECTED_SLOTS = [
    ("SLOT-001", "2026-09-14T14:00:00Z", "2026-09-14T14:30:00Z", "occupied"),
    ("SLOT-002", "2026-09-14T14:30:00Z", "2026-09-14T15:00:00Z", "available"),
    ("SLOT-003", "2026-09-14T15:00:00Z", "2026-09-14T15:30:00Z", "available"),
    ("SLOT-004", "2026-09-14T15:30:00Z", "2026-09-14T16:00:00Z", "occupied"),
    ("SLOT-005", "2026-09-15T14:00:00Z", "2026-09-15T14:30:00Z", "available"),
    ("SLOT-006", "2026-09-15T14:30:00Z", "2026-09-15T15:00:00Z", "occupied"),
    ("SLOT-007", "2026-09-15T15:00:00Z", "2026-09-15T15:30:00Z", "available"),
    ("SLOT-008", "2026-09-15T15:30:00Z", "2026-09-15T16:00:00Z", "available"),
]


def _assert_documented_schedule(session: Session) -> None:
    slots = session.scalars(
        select(AppointmentSlot).order_by(AppointmentSlot.starts_at, AppointmentSlot.id)
    ).all()
    assert [(slot.id, slot.starts_at, slot.ends_at, slot.status) for slot in slots] == (
        EXPECTED_SLOTS
    )
    assert {slot.dentist_name for slot in slots} == {DENTIST}
    occupied_ids = {slot.id for slot in slots if slot.status == "occupied"}
    available_ids = {slot.id for slot in slots if slot.status == "available"}
    assert occupied_ids == {"SLOT-001", "SLOT-004", "SLOT-006"}
    assert available_ids == {"SLOT-002", "SLOT-003", "SLOT-005", "SLOT-007", "SLOT-008"}
    assert session.scalars(select(Appointment)).all() == []


def _dirty_calendar(session: Session) -> None:
    booked = session.get(AppointmentSlot, "SLOT-002")
    assert booked is not None
    booked.status = "occupied"
    session.add(
        Appointment(
            id="APT-001",
            slot_id="SLOT-002",
            patient_name="Jordan Hale",
            status="active",
            created_at="2026-09-09T12:00:00Z",
        )
    )
    session.add(
        IdempotencyRecord(
            key="call_abc:booking",
            request_fingerprint="fingerprint-a",
            appointment_id="APT-001",
            created_at="2026-09-09T12:00:01Z",
        )
    )
    session.add(
        RequestEvent(
            created_at="2026-09-09T12:00:03Z",
            attempt_number=1,
            event_type="appointment_result",
            outcome="created",
            appointment_id="APT-001",
            idempotency_key="call_abc:booking",
            call_id="call_abc",
        )
    )
    session.add(
        AppointmentSlot(
            id="SLOT-999",
            dentist_name="Dr. Extra",
            starts_at="2026-09-16T14:00:00Z",
            ends_at="2026-09-16T14:30:00Z",
            status="available",
        )
    )
    session.commit()


def _client(tmp_path: Path, *, live_demo_enabled: bool):
    settings = Settings(
        database_path=tmp_path / "calendar.sqlite",
        live_demo_enabled=live_demo_enabled,
        _env_file=None,
    )
    return TestClient(create_app(settings))


def test_startup_seeds_empty_database_with_documented_schedule(tmp_path: Path):
    with _client(tmp_path, live_demo_enabled=False) as client:
        response = client.get("/health")
        with client.app.state.session_factory() as session:
            _assert_documented_schedule(session)

    assert response.status_code == 200


def test_seed_if_empty_does_not_overwrite_existing_slots(tmp_path: Path):
    engine = init_db(tmp_path / "calendar.sqlite")
    with Session(engine) as session:
        session.add(
            AppointmentSlot(
                id="SLOT-KEEP",
                dentist_name="Dr. Other",
                starts_at="2026-09-20T10:00:00Z",
                ends_at="2026-09-20T10:30:00Z",
                status="available",
            )
        )
        session.commit()
        inserted = seed_if_empty(session)
        slots = session.scalars(select(AppointmentSlot)).all()

    engine.dispose()
    assert inserted == 0
    assert [(slot.id, slot.dentist_name) for slot in slots] == [("SLOT-KEEP", "Dr. Other")]


def test_reset_restores_seed_and_removes_demo_records(tmp_path: Path):
    engine = init_db(tmp_path / "calendar.sqlite")
    with Session(engine) as session:
        seed_if_empty(session)
        _dirty_calendar(session)
        reset_calendar(session)
        _assert_documented_schedule(session)
        assert session.scalars(select(IdempotencyRecord)).all() == []
        assert session.scalars(select(RequestEvent)).all() == []
        assert session.scalar(select(func.count()).select_from(AppointmentSlot)) == 8

    engine.dispose()


def test_reset_http_is_forbidden_when_live_demo_is_disabled(tmp_path: Path):
    with _client(tmp_path, live_demo_enabled=False) as client:
        with client.app.state.session_factory() as session:
            _dirty_calendar(session)

        response = client.post("/api/demo/reset")

        with client.app.state.session_factory() as session:
            assert session.get(Appointment, "APT-001") is not None
            assert session.get(AppointmentSlot, "SLOT-999") is not None
            assert session.get(AppointmentSlot, "SLOT-002").status == "occupied"

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Calendar reset is unavailable while the public live demo is paused."
    }
    assert "LIVE_DEMO" not in response.text


def test_reset_http_restores_schedule_when_live_demo_is_enabled(tmp_path: Path):
    with _client(tmp_path, live_demo_enabled=True) as client:
        with client.app.state.session_factory() as session:
            _dirty_calendar(session)

        response = client.post("/api/demo/reset")

        with client.app.state.session_factory() as session:
            _assert_documented_schedule(session)
            assert session.scalars(select(IdempotencyRecord)).all() == []
            assert session.scalars(select(RequestEvent)).all() == []

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reset"
    assert body["dentist_name"] == DENTIST
    assert body["demo_dates"] == DEMO_DATES
    assert [
        (slot["id"], slot["starts_at"], slot["ends_at"], slot["status"])
        for slot in body["slots"]
    ] == EXPECTED_SLOTS
    assert {slot["dentist_name"] for slot in body["slots"]} == {DENTIST}
