from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import init_db
from app.main import create_app
from app.models import Appointment, AppointmentSlot, IdempotencyRecord, RequestEvent
from app.settings import Settings

EXPECTED_TABLES = {
    "appointment_slot",
    "appointment",
    "idempotency_record",
    "request_event",
}


def _slot(**overrides) -> AppointmentSlot:
    values = {
        "id": "SLOT-001",
        "dentist_name": "Dr. Elena Voss",
        "starts_at": "2026-09-14T14:00:00Z",
        "ends_at": "2026-09-14T14:30:00Z",
        "status": "available",
    }
    values.update(overrides)
    return AppointmentSlot(**values)


def _appointment(**overrides) -> Appointment:
    values = {
        "id": "APT-001",
        "slot_id": "SLOT-001",
        "patient_name": "Jordan Hale",
        "status": "active",
        "created_at": "2026-09-09T12:00:00Z",
    }
    values.update(overrides)
    return Appointment(**values)


@pytest.fixture
def engine(tmp_path: Path):
    db_engine = init_db(tmp_path / "calendar.sqlite")
    yield db_engine
    db_engine.dispose()


def test_init_db_creates_sqlite_file_and_tables(tmp_path: Path):
    database_path = tmp_path / "nested" / "calendar.sqlite"

    engine = init_db(database_path)

    assert database_path.exists()
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
    engine.dispose()


def test_app_startup_creates_database_without_manual_sql(tmp_path: Path):
    database_path = tmp_path / "calendar.sqlite"
    settings = Settings(database_path=database_path, _env_file=None)
    application = create_app(settings)

    with TestClient(application) as client:
        response = client.get("/health")
        table_names = set(inspect(application.state.engine).get_table_names())

    assert response.status_code == 200
    assert database_path.exists()
    assert table_names == EXPECTED_TABLES


def test_sqlite_enables_wal_and_foreign_keys(engine):
    with engine.connect() as connection:
        journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar()
        foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar()

    assert journal_mode.lower() == "wal"
    assert foreign_keys == 1


def test_appointment_slots_store_stable_ids_and_availability(engine):
    slot = _slot()

    with Session(engine) as session:
        session.add(slot)
        session.commit()
        stored = session.get(AppointmentSlot, "SLOT-001")
        assert stored is not None
        assert stored.id == "SLOT-001"
        assert stored.starts_at == "2026-09-14T14:00:00Z"
        assert stored.ends_at == "2026-09-14T14:30:00Z"
        assert stored.status == "available"


def test_occupied_slot_does_not_require_an_appointment(engine):
    with Session(engine) as session:
        session.add(_slot(status="occupied"))
        session.commit()
        stored = session.get(AppointmentSlot, "SLOT-001")
        assert stored is not None
        assert stored.status == "occupied"
        assert stored.appointments == []


def test_appointments_reference_slots_with_stable_public_ids(engine):
    with Session(engine) as session:
        session.add(_slot())
        session.add(_appointment())
        session.commit()
        stored = session.get(Appointment, "APT-001")
        assert stored is not None
        assert stored.id == "APT-001"
        assert stored.slot_id == "SLOT-001"
        assert stored.patient_name == "Jordan Hale"
        assert stored.status == "active"


def test_appointment_requires_an_existing_slot(engine):
    with Session(engine) as session:
        session.add(_appointment())
        with pytest.raises(IntegrityError):
            session.commit()


def test_duplicate_idempotency_keys_are_rejected(engine):
    with Session(engine) as session:
        session.add(_slot())
        session.add(_appointment())
        session.add(
            IdempotencyRecord(
                key="call_abc:booking",
                request_fingerprint="fingerprint-a",
                appointment_id="APT-001",
                created_at="2026-09-09T12:00:01Z",
            )
        )
        session.commit()

        session.add(
            IdempotencyRecord(
                key="call_abc:booking",
                request_fingerprint="fingerprint-b",
                appointment_id="APT-001",
                created_at="2026-09-09T12:00:02Z",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_slot_cannot_hold_two_active_appointments(engine):
    with Session(engine) as session:
        session.add(_slot())
        session.add(_appointment())
        session.commit()

        session.add(
            _appointment(
                id="APT-002",
                patient_name="Sam Rivera",
                created_at="2026-09-09T12:01:00Z",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_request_events_record_attempt_outcome_and_appointment(engine):
    with Session(engine) as session:
        session.add(_slot())
        session.add(_appointment())
        session.add(
            RequestEvent(
                created_at="2026-09-09T12:00:03Z",
                attempt_number=2,
                event_type="appointment_result",
                outcome="replayed",
                appointment_id="APT-001",
                idempotency_key="call_abc:booking",
                call_id="call_abc",
            )
        )
        session.commit()
        stored = session.scalars(select(RequestEvent)).one()
        assert stored.id == 1
        assert stored.created_at == "2026-09-09T12:00:03Z"
        assert stored.attempt_number == 2
        assert stored.event_type == "appointment_result"
        assert stored.outcome == "replayed"
        assert stored.appointment_id == "APT-001"
        assert stored.idempotency_key == "call_abc:booking"
        assert stored.call_id == "call_abc"
