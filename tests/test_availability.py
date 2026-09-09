from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.availability import AvailabilityQueryError, list_available_slots
from app.db import init_db
from app.main import create_app
from app.models import AppointmentSlot
from app.seed import seed_if_empty
from app.settings import Settings

DENTIST = "Dr. Elena Voss"
MONDAY_OPEN = [
    ("SLOT-002", "2026-09-14T14:30:00Z", "2026-09-14T15:00:00Z"),
    ("SLOT-003", "2026-09-14T15:00:00Z", "2026-09-14T15:30:00Z"),
]
TUESDAY_OPEN = [
    ("SLOT-005", "2026-09-15T14:00:00Z", "2026-09-15T14:30:00Z"),
    ("SLOT-007", "2026-09-15T15:00:00Z", "2026-09-15T15:30:00Z"),
    ("SLOT-008", "2026-09-15T15:30:00Z", "2026-09-15T16:00:00Z"),
]


def _client(tmp_path: Path):
    settings = Settings(
        database_path=tmp_path / "calendar.sqlite",
        live_demo_enabled=False,
        _env_file=None,
    )
    return TestClient(create_app(settings))


def _slot_triples(slots: list[dict]) -> list[tuple[str, str, str]]:
    return [(slot["id"], slot["starts_at"], slot["ends_at"]) for slot in slots]


def test_availability_http_returns_open_monday_slots(tmp_path: Path):
    with _client(tmp_path) as client:
        response = client.get("/api/availability", params={"date": "2026-09-14"})

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-09-14"
    assert body["dentist_name"] == DENTIST
    assert _slot_triples(body["slots"]) == MONDAY_OPEN
    assert {slot["status"] for slot in body["slots"]} == {"available"}
    assert {slot["id"] for slot in body["slots"]}.isdisjoint(
        {"SLOT-001", "SLOT-004", "SLOT-006"}
    )


def test_availability_http_returns_open_tuesday_slots(tmp_path: Path):
    with _client(tmp_path) as client:
        response = client.get("/api/availability", params={"date": "2026-09-15"})

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-09-15"
    assert _slot_triples(body["slots"]) == TUESDAY_OPEN
    assert {slot["status"] for slot in body["slots"]} == {"available"}


def test_occupied_slot_disappears_from_availability(tmp_path: Path):
    with _client(tmp_path) as client:
        with client.app.state.session_factory() as session:
            slot = session.get(AppointmentSlot, "SLOT-002")
            assert slot is not None
            slot.status = "occupied"
            session.commit()

        response = client.get("/api/availability", params={"date": "2026-09-14"})

    assert response.status_code == 200
    assert _slot_triples(response.json()["slots"]) == [
        ("SLOT-003", "2026-09-14T15:00:00Z", "2026-09-14T15:30:00Z")
    ]


def test_invalid_dates_return_structured_client_error(tmp_path: Path):
    with _client(tmp_path) as client:
        responses = [
            client.get("/api/availability"),
            client.get("/api/availability", params={"date": ""}),
            client.get("/api/availability", params={"date": "next Tuesday"}),
            client.get("/api/availability", params={"date": "2026-09-14T14:00:00Z"}),
            client.get("/api/availability", params={"date": "14/09/2026"}),
        ]

    for response in responses:
        assert response.status_code == 400
        assert response.json() == {
            "detail": {
                "error": "invalid_date",
                "message": "Date must be an ISO calendar date (YYYY-MM-DD).",
            }
        }


def test_unsupported_date_returns_structured_client_error(tmp_path: Path):
    with _client(tmp_path) as client:
        response = client.get("/api/availability", params={"date": "2026-09-16"})

    assert response.status_code == 400
    assert response.json() == {
        "detail": {
            "error": "unsupported_date",
            "message": "Availability can only be queried for 2026-09-14 or 2026-09-15.",
        }
    }


def test_list_available_slots_is_calendar_lookup_not_retell_parsing(tmp_path: Path):
    engine = init_db(tmp_path / "calendar.sqlite")
    with Session(engine) as session:
        seed_if_empty(session)
        result = list_available_slots(session, "2026-09-14")
        with pytest.raises(AvailabilityQueryError) as wrapped:
            list_available_slots(session, {"args": {"date": "2026-09-14"}})

    engine.dispose()
    assert _slot_triples(result["slots"]) == MONDAY_OPEN
    assert wrapped.value.error == "invalid_date"
