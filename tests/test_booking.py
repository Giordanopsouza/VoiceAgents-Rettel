import inspect
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.availability import list_available_slots
from app.booking import BookingError, book_appointment
from app.db import init_db
from app.models import Appointment, AppointmentSlot, IdempotencyRecord
from app.seed import seed_if_empty

BOOKING_PARAMS = {"session", "idempotency_key", "slot_id", "patient_name"}
APPOINTMENT_COLUMNS = {"id", "slot_id", "patient_name", "status", "created_at"}


@pytest.fixture
def engine(tmp_path: Path):
    db_engine = init_db(tmp_path / "calendar.sqlite")
    with Session(db_engine) as session:
        seed_if_empty(session)
    yield db_engine
    db_engine.dispose()


def _book(engine, **kwargs):
    with Session(engine) as session:
        return book_appointment(session, **kwargs)


def _count_appointments(engine) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(Appointment)) or 0


def test_first_valid_booking_creates_one_appointment_with_stable_id(engine):
    result = _book(
        engine,
        idempotency_key="call_abc:booking",
        slot_id="SLOT-002",
        patient_name="Jordan Hale",
    )

    appointment = result["appointment"]
    assert result["replayed"] is False
    assert appointment["id"] == "APT-001"
    assert appointment["slot_id"] == "SLOT-002"
    assert appointment["patient_name"] == "Jordan Hale"
    assert appointment["status"] == "active"
    assert appointment["created_at"].endswith("Z")

    with Session(engine) as session:
        stored = session.get(Appointment, "APT-001")
        slot = session.get(AppointmentSlot, "SLOT-002")
        record = session.get(IdempotencyRecord, "call_abc:booking")
        open_ids = {item["id"] for item in list_available_slots(session, "2026-09-14")["slots"]}

    assert stored is not None
    assert stored.id == "APT-001"
    assert stored.patient_name == "Jordan Hale"
    assert slot is not None and slot.status == "occupied"
    assert record is not None
    assert record.appointment_id == "APT-001"
    assert _count_appointments(engine) == 1
    assert "SLOT-002" not in open_ids


def test_repeat_same_key_and_payload_returns_original_without_second_row(engine):
    first = _book(
        engine,
        idempotency_key="call_abc:booking",
        slot_id="SLOT-002",
        patient_name="Jordan Hale",
    )
    second = _book(
        engine,
        idempotency_key="call_abc:booking",
        slot_id="SLOT-002",
        patient_name="  Jordan Hale  ",
    )

    assert first["replayed"] is False
    assert second["replayed"] is True
    assert second["appointment"] == first["appointment"]
    assert _count_appointments(engine) == 1

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(IdempotencyRecord)) == 1
        assert session.get(AppointmentSlot, "SLOT-002").status == "occupied"


def test_reuse_key_with_different_payload_returns_conflict(engine):
    _book(
        engine,
        idempotency_key="call_abc:booking",
        slot_id="SLOT-002",
        patient_name="Jordan Hale",
    )

    with pytest.raises(BookingError) as different_slot:
        _book(
            engine,
            idempotency_key="call_abc:booking",
            slot_id="SLOT-003",
            patient_name="Jordan Hale",
        )
    with pytest.raises(BookingError) as different_patient:
        _book(
            engine,
            idempotency_key="call_abc:booking",
            slot_id="SLOT-002",
            patient_name="Sam Rivera",
        )

    assert different_slot.value.error == "idempotency_conflict"
    assert different_patient.value.error == "idempotency_conflict"
    assert _count_appointments(engine) == 1

    with Session(engine) as session:
        assert session.get(AppointmentSlot, "SLOT-002").status == "occupied"
        assert session.get(AppointmentSlot, "SLOT-003").status == "available"


def test_competing_requests_cannot_create_two_active_appointments(engine):
    barrier = Barrier(2)

    def attempt(key: str, name: str):
        barrier.wait(timeout=5)
        return _book(
            engine,
            idempotency_key=key,
            slot_id="SLOT-002",
            patient_name=name,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(attempt, "call_a:booking", "Jordan Hale"),
            pool.submit(attempt, "call_b:booking", "Sam Rivera"),
        ]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(("ok", future.result()))
            except BookingError as exc:
                outcomes.append(("error", exc))

    successes = [result for status, result in outcomes if status == "ok"]
    failures = [result for status, result in outcomes if status == "error"]
    assert len(successes) == 1
    assert len(failures) == 1
    assert failures[0].error == "slot_unavailable"
    assert _count_appointments(engine) == 1

    with Session(engine) as session:
        appointments = session.scalars(select(Appointment)).all()
        assert len(appointments) == 1
        assert appointments[0].slot_id == "SLOT-002"
        assert session.get(AppointmentSlot, "SLOT-002").status == "occupied"


def test_unknown_or_unavailable_slot_returns_structured_error(engine):
    with pytest.raises(BookingError) as unknown:
        _book(
            engine,
            idempotency_key="call_abc:booking",
            slot_id="SLOT-999",
            patient_name="Jordan Hale",
        )
    with pytest.raises(BookingError) as occupied:
        _book(
            engine,
            idempotency_key="call_abc:booking",
            slot_id="SLOT-001",
            patient_name="Jordan Hale",
        )

    _book(
        engine,
        idempotency_key="call_abc:booking",
        slot_id="SLOT-002",
        patient_name="Jordan Hale",
    )
    with pytest.raises(BookingError) as taken:
        _book(
            engine,
            idempotency_key="call_def:booking",
            slot_id="SLOT-002",
            patient_name="Sam Rivera",
        )

    assert unknown.value.error == "unknown_slot"
    assert occupied.value.error == "slot_unavailable"
    assert taken.value.error == "slot_unavailable"
    assert _count_appointments(engine) == 1


def test_booking_requires_only_a_fictional_patient_name(engine):
    params = inspect.signature(book_appointment).parameters
    result = _book(
        engine,
        idempotency_key="call_abc:booking",
        slot_id="SLOT-002",
        patient_name="Jordan Hale",
    )

    with pytest.raises(BookingError) as missing_name:
        _book(
            engine,
            idempotency_key="call_def:booking",
            slot_id="SLOT-003",
            patient_name="   ",
        )

    with Session(engine) as session:
        stored = session.get(Appointment, result["appointment"]["id"])

    assert set(params) == BOOKING_PARAMS
    assert {column.name for column in Appointment.__table__.columns} == APPOINTMENT_COLUMNS
    assert stored is not None
    assert stored.patient_name == "Jordan Hale"
    assert not hasattr(stored, "phone")
    assert not hasattr(stored, "email")
    assert missing_name.value.error == "invalid_patient_name"
    assert _count_appointments(engine) == 1


def test_book_appointment_is_calendar_logic_not_retell_parsing(engine):
    with pytest.raises(BookingError) as wrapped:
        _book(
            engine,
            idempotency_key={"call": {"call_id": "call_abc"}},
            slot_id={"args": {"slot_id": "SLOT-002"}},
            patient_name={"args": {"patient_name": "Jordan Hale"}},
        )

    assert wrapped.value.error == "invalid_idempotency_key"
    assert _count_appointments(engine) == 0
