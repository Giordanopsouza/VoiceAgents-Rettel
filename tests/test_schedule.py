from pathlib import Path

from fastapi.testclient import TestClient

from app.events import record_booking_attempt
from app.main import create_app
from app.settings import Settings
from tests.test_seed import DENTIST, DEMO_DATES, EXPECTED_SLOTS, _dirty_calendar


def _client(tmp_path: Path, *, live_demo_enabled: bool = False):
    settings = Settings(
        database_path=tmp_path / "calendar.sqlite",
        live_demo_enabled=live_demo_enabled,
        _env_file=None,
    )
    return TestClient(create_app(settings))


def _slot_tuples(slots: list[dict]) -> list[tuple[str, str, str, str]]:
    return [
        (slot["id"], slot["starts_at"], slot["ends_at"], slot["status"])
        for slot in slots
    ]


def test_schedule_http_returns_available_and_occupied_seed_slots(tmp_path: Path):
    with _client(tmp_path) as client:
        response = client.get("/api/schedule")

    assert response.status_code == 200
    body = response.json()
    assert body["dentist_name"] == DENTIST
    assert body["demo_dates"] == DEMO_DATES
    assert _slot_tuples(body["slots"]) == EXPECTED_SLOTS
    assert {slot["status"] for slot in body["slots"]} == {"available", "occupied"}
    assert {slot["id"] for slot in body["slots"] if slot["status"] == "occupied"} == {
        "SLOT-001",
        "SLOT-004",
        "SLOT-006",
    }


def test_schedule_http_stays_readable_when_live_demo_is_paused(tmp_path: Path):
    with _client(tmp_path, live_demo_enabled=False) as client:
        response = client.get("/api/schedule")

    assert response.status_code == 200
    assert _slot_tuples(response.json()["slots"]) == EXPECTED_SLOTS


def test_schedule_http_reflects_a_booking_then_reset(tmp_path: Path):
    with _client(tmp_path, live_demo_enabled=True) as client:
        with client.app.state.session_factory() as session:
            record_booking_attempt(
                session,
                call_id="call_abc",
                idempotency_key="call_abc:booking",
                slot_id="SLOT-002",
                patient_name="Jordan Hale",
            )
        after_booking = client.get("/api/schedule")
        reset = client.post("/api/demo/reset")
        after_reset = client.get("/api/schedule")

    booked = next(
        slot for slot in after_booking.json()["slots"] if slot["id"] == "SLOT-002"
    )
    assert after_booking.status_code == 200
    assert booked["status"] == "occupied"
    assert reset.status_code == 200
    assert _slot_tuples(reset.json()["slots"]) == EXPECTED_SLOTS
    assert _slot_tuples(after_reset.json()["slots"]) == EXPECTED_SLOTS


def test_schedule_http_does_not_write_timeline_events(tmp_path: Path):
    with _client(tmp_path) as client:
        lookup = client.get("/api/schedule")
        events = client.get("/api/events")

    assert lookup.status_code == 200
    assert events.json()["events"] == []


def test_dirty_calendar_is_visible_on_schedule_read(tmp_path: Path):
    with _client(tmp_path, live_demo_enabled=True) as client:
        with client.app.state.session_factory() as session:
            _dirty_calendar(session)
        response = client.get("/api/schedule")

    ids = {slot["id"] for slot in response.json()["slots"]}
    booked = next(
        slot for slot in response.json()["slots"] if slot["id"] == "SLOT-002"
    )
    assert "SLOT-999" in ids
    assert booked["status"] == "occupied"
