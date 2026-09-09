import hashlib
import hmac
import json
import re
import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import create_app
from app.models import Appointment
from app.retell_auth import RETELL_SIGNATURE_HEADER
from app.retell_booking import derive_idempotency_key, unwrap_booking_request
from app.settings import Settings

TEST_API_KEY = "test-retell-api-key"
OTHER_API_KEY = "other-retell-api-key"
PATH = "/retell/book_appointment"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "retell" / "book_appointment.json"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiJ9.secret-access-token"
TRANSCRIPT = "Agent: Please confirm 2:30 PM with Dr. Elena Voss.\nUser: Yes, book it."
SAFE_KEY = re.compile(r"^bk_[0-9a-f]{64}$")
CANONICAL_KEY = "bk_be163e9b6c7e833f09eb13223e2f0edb0f256169963ea630ba75cf873bd732d0"
TIMEOUT_SECONDS = 0.05
DELAY_SECONDS = 0.25
MONDAY_CREATED = {
    "ok": True,
    "replayed": False,
    "appointment_id": "APT-001",
    "slot_id": "SLOT-002",
    "dentist_name": "Dr. Elena Voss",
    "date": "2026-09-14",
    "date_label": "Monday, September 14, 2026",
    "time_label": "2:30 PM",
    "message": (
        "Appointment APT-001 is booked for Monday, September 14, 2026 at 2:30 PM. "
        "Tell the caller once. Do not ask them to confirm again."
    ),
}
MONDAY_REPLAYED = {
    **MONDAY_CREATED,
    "replayed": True,
    "message": (
        "Appointment APT-001 was already booked on the first attempt "
        "for Monday, September 14, 2026 at 2:30 PM. Tell the caller once. "
        "Do not ask them to confirm again."
    ),
}


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _sign(body: str, api_key: str = TEST_API_KEY, timestamp_ms: int | None = None) -> str:
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    digest = hmac.new(
        api_key.encode("utf-8"),
        f"{body}{timestamp_ms}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"v={timestamp_ms},d={digest}"


def _wrapped(
    *,
    slot_id: object | None = "SLOT-002",
    patient_name: object | None = "Jordan Hale",
    dentist_name: object | None = "Dr. Elena Voss",
    confirmed: object | None = True,
    call_id: object = "call_abc",
    include_call: bool = True,
) -> dict:
    args: dict = {}
    if slot_id is not None:
        args["slot_id"] = slot_id
    if patient_name is not None:
        args["patient_name"] = patient_name
    if dentist_name is not None:
        args["dentist_name"] = dentist_name
    if confirmed is not None:
        args["confirmed"] = confirmed
    payload: dict = {"name": "book_appointment", "args": args}
    if include_call:
        payload["call"] = {
            "call_id": call_id,
            "call_type": "web_call",
            "access_token": ACCESS_TOKEN,
            "transcript": TRANSCRIPT,
        }
    return payload


def _client(tmp_path: Path, *, retell_api_key: str = TEST_API_KEY):
    settings = Settings(
        database_path=tmp_path / "calendar.sqlite",
        retell_api_key=retell_api_key,
        retell_function_timeout_seconds=TIMEOUT_SECONDS,
        failure_lab_delay_seconds=DELAY_SECONDS,
        _env_file=None,
    )
    return TestClient(create_app(settings))


def _post(client: TestClient, payload: dict | str, signature: str | None):
    body = payload if isinstance(payload, str) else json.dumps(payload)
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers[RETELL_SIGNATURE_HEADER] = signature
    return client.post(PATH, content=body, headers=headers)


def _assert_secrets_omitted(response, signature: str | None = None) -> None:
    text = response.text
    assert TEST_API_KEY not in text
    assert OTHER_API_KEY not in text
    assert ACCESS_TOKEN not in text
    assert "secret-access-token" not in text
    assert TRANSCRIPT not in text
    assert "book it" not in text
    if signature:
        assert signature not in text
        digest = signature.split("d=", 1)[-1]
        assert digest not in text


def test_tool_schema_requires_explicit_confirmation_data():
    schema = _schema()
    parameters = schema["parameters"]

    assert schema["name"] == "book_appointment"
    assert schema["http"] == {"method": "POST", "path": PATH}
    assert parameters["type"] == "object"
    assert parameters["required"] == [
        "slot_id",
        "patient_name",
        "dentist_name",
        "confirmed",
    ]
    assert parameters["properties"]["confirmed"]["type"] == "boolean"
    assert parameters["properties"]["slot_id"]["type"] == "string"
    assert parameters["properties"]["patient_name"]["type"] == "string"
    assert parameters["properties"]["dentist_name"]["type"] == "string"
    assert "explicitly confirms" in schema["description"]
    assert "another verbal confirmation" in schema["description"]
    assert "phone" in parameters["properties"]["patient_name"]["description"]
    assert "confirmed is false" in parameters["properties"]["confirmed"]["description"]


def test_signed_confirmed_booking_creates_speakable_appointment(tmp_path: Path):
    payload = _wrapped()
    body = json.dumps(payload)
    with _client(tmp_path) as client:
        response = _post(client, body, _sign(body))
        events = client.get("/api/events")
        availability = client.get("/api/availability", params={"date": "2026-09-14"})

    assert response.status_code == 200
    assert response.json() == MONDAY_CREATED
    assert [event["event_type"] for event in events.json()["events"]] == [
        "receipt",
        "idempotency_decision",
        "appointment_result",
        "response_outcome",
    ]
    assert {event["call_id"] for event in events.json()["events"]} == {"call_abc"}
    assert {event["idempotency_key"] for event in events.json()["events"]} == {CANONICAL_KEY}
    assert {event["appointment_id"] for event in events.json()["events"][1:]} == {"APT-001"}
    assert "SLOT-002" not in {slot["id"] for slot in availability.json()["slots"]}
    _assert_secrets_omitted(response)
    _assert_secrets_omitted(events)
    assert "Jordan Hale" not in events.text


def test_retry_returns_same_appointment_without_asking_to_confirm_again(tmp_path: Path):
    payload = _wrapped()
    body = json.dumps(payload)
    with _client(tmp_path) as client:
        first = _post(client, body, _sign(body))
        second = _post(client, body, _sign(body))
        events = client.get("/api/events")
        with client.app.state.session_factory() as session:
            appointment_count = session.scalar(select(func.count()).select_from(Appointment))

    assert first.status_code == 200
    assert first.json() == MONDAY_CREATED
    assert second.status_code == 200
    assert second.json() == MONDAY_REPLAYED
    assert first.json()["appointment_id"] == second.json()["appointment_id"] == "APT-001"
    assert appointment_count == 1
    outcomes = [
        event["outcome"]
        for event in events.json()["events"]
        if event["event_type"] == "response_outcome"
    ]
    assert outcomes == ["created_returned", "duplicate_returned"]
    assert {event["idempotency_key"] for event in events.json()["events"]} == {CANONICAL_KEY}
    _assert_secrets_omitted(first)
    _assert_secrets_omitted(second)


def test_unsigned_and_invalid_signatures_are_rejected(tmp_path: Path):
    payload = _wrapped()
    body = json.dumps(payload)
    with _client(tmp_path) as client:
        missing = _post(client, body, None)
        invalid = _post(client, body, _sign(body, api_key=OTHER_API_KEY))
        events = client.get("/api/events")
        availability = client.get("/api/availability", params={"date": "2026-09-14"})

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert missing.json() == {"detail": {"message": "Unauthorized"}}
    assert invalid.json() == {"detail": {"message": "Unauthorized"}}
    assert events.json() == {"events": []}
    assert "SLOT-002" in {slot["id"] for slot in availability.json()["slots"]}
    _assert_secrets_omitted(missing)
    _assert_secrets_omitted(invalid, _sign(body, api_key=OTHER_API_KEY))


def test_unconfirmed_request_does_not_book(tmp_path: Path):
    schema = _schema()
    payload = _wrapped(confirmed=False)
    body = json.dumps(payload)
    with _client(tmp_path) as client:
        response = _post(client, body, _sign(body))
        events = client.get("/api/events")
        availability = client.get("/api/availability", params={"date": "2026-09-14"})

    assert "confirmed" in schema["parameters"]["required"]
    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "error": "confirmation_required",
        "message": (
            "Booking requires confirmed=true after the caller explicitly confirms "
            "dentist, date, and time."
        ),
    }
    assert events.json() == {"events": []}
    assert "SLOT-002" in {slot["id"] for slot in availability.json()["slots"]}
    _assert_secrets_omitted(response)


def test_required_schema_argument_missing_returns_bounded_agent_error(tmp_path: Path):
    payload = _wrapped(slot_id=None, patient_name=None, dentist_name=None, confirmed=None)
    body = json.dumps(payload)
    with _client(tmp_path) as client:
        response = _post(client, body, _sign(body))
        events = client.get("/api/events")

    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "error": "invalid_request",
        "message": (
            "Function arguments must include slot_id, patient_name, dentist_name, "
            "and confirmed."
        ),
    }
    assert events.json() == {"events": []}
    _assert_secrets_omitted(response)


def test_unwrapped_args_only_payload_returns_bounded_agent_error(tmp_path: Path):
    payload = {
        "slot_id": "SLOT-002",
        "patient_name": "Jordan Hale",
        "dentist_name": "Dr. Elena Voss",
        "confirmed": True,
    }
    body = json.dumps(payload)
    with _client(tmp_path) as client:
        response = _post(client, body, _sign(body))

    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "error": "invalid_request",
        "message": (
            "Request must be Retell's wrapped custom-function payload with "
            "args.slot_id, args.patient_name, args.dentist_name, and args.confirmed."
        ),
    }
    _assert_secrets_omitted(response)


def test_unknown_dentist_and_unavailable_slot_return_bounded_agent_errors(tmp_path: Path):
    other_dentist = _wrapped(dentist_name="Dr. Other")
    occupied = _wrapped(slot_id="SLOT-001")
    with _client(tmp_path) as client:
        dentist_body = json.dumps(other_dentist)
        occupied_body = json.dumps(occupied)
        dentist_response = _post(client, dentist_body, _sign(dentist_body))
        occupied_response = _post(client, occupied_body, _sign(occupied_body))
        events = client.get("/api/events")

    assert dentist_response.status_code == 200
    assert dentist_response.json() == {
        "ok": False,
        "error": "invalid_dentist",
        "message": "This clinic only books with Dr. Elena Voss.",
    }
    assert occupied_response.status_code == 200
    assert occupied_response.json() == {
        "ok": False,
        "error": "slot_unavailable",
        "message": "The requested appointment slot is not available.",
    }
    assert events.json()["events"]
    assert "Dr. Other" not in dentist_response.text
    _assert_secrets_omitted(dentist_response)
    _assert_secrets_omitted(occupied_response)


def test_normalized_patient_name_and_dentist_share_the_same_key(tmp_path: Path):
    first = _wrapped(patient_name="  Jordan   Hale  ", dentist_name="dr. elena voss")
    second = _wrapped(patient_name="JORDAN HALE", dentist_name="Dr. Elena Voss")
    with _client(tmp_path) as client:
        first_body = json.dumps(first)
        second_body = json.dumps(second)
        created = _post(client, first_body, _sign(first_body))
        replayed = _post(client, second_body, _sign(second_body))
        events = client.get("/api/events")

    assert created.json()["replayed"] is False
    assert replayed.json()["replayed"] is True
    assert {event["idempotency_key"] for event in events.json()["events"]} == {CANONICAL_KEY}


def test_idempotency_key_includes_call_slot_dentist_and_normalized_patient():
    base = derive_idempotency_key(
        call_id="call_abc",
        slot_id="SLOT-002",
        dentist_name="Dr. Elena Voss",
        patient_name="Jordan Hale",
    )
    spaced = derive_idempotency_key(
        call_id="call_abc",
        slot_id="SLOT-002",
        dentist_name="  Dr.  Elena Voss ",
        patient_name="  Jordan   Hale  ",
    )

    assert base == CANONICAL_KEY
    assert spaced == base
    assert SAFE_KEY.fullmatch(base)
    assert "Jordan Hale" not in base
    assert " " not in base
    assert derive_idempotency_key(
        call_id="call_other",
        slot_id="SLOT-002",
        dentist_name="Dr. Elena Voss",
        patient_name="Jordan Hale",
    ) != base
    assert derive_idempotency_key(
        call_id="call_abc",
        slot_id="SLOT-003",
        dentist_name="Dr. Elena Voss",
        patient_name="Jordan Hale",
    ) != base
    assert derive_idempotency_key(
        call_id="call_abc",
        slot_id="SLOT-002",
        dentist_name="Dr. Other",
        patient_name="Jordan Hale",
    ) != base
    assert derive_idempotency_key(
        call_id="call_abc",
        slot_id="SLOT-002",
        dentist_name="Dr. Elena Voss",
        patient_name="Sam Rivera",
    ) != base


def test_unwrap_requires_wrapped_confirmation_and_call_id():
    booking = unwrap_booking_request(_wrapped(patient_name="  Jordan   Hale  "))

    assert booking.call_id == "call_abc"
    assert booking.slot_id == "SLOT-002"
    assert booking.dentist_name == "Dr. Elena Voss"
    assert booking.patient_name == "jordan hale"


def test_missing_call_id_returns_bounded_agent_error(tmp_path: Path):
    payload = _wrapped(include_call=False)
    body = json.dumps(payload)
    with _client(tmp_path) as client:
        response = _post(client, body, _sign(body))
        events = client.get("/api/events")

    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "error": "invalid_request",
        "message": "Request must include call.call_id.",
    }
    assert events.json() == {"events": []}
    _assert_secrets_omitted(response)


def test_failure_lab_delays_first_booking_then_replays_without_duplicate(tmp_path: Path):
    payload = _wrapped()
    body = json.dumps(payload)
    with _client(tmp_path) as client:
        enabled = client.put("/api/failure-lab", json={"enabled": True})
        started = time.monotonic()
        first = _post(client, body, _sign(body))
        first_elapsed = time.monotonic() - started
        started = time.monotonic()
        second = _post(client, body, _sign(body))
        retry_elapsed = time.monotonic() - started
        events = client.get("/api/events")
        with client.app.state.session_factory() as session:
            appointment_count = session.scalar(select(func.count()).select_from(Appointment))

    assert enabled.status_code == 200
    assert first.json() == MONDAY_CREATED
    assert second.json() == MONDAY_REPLAYED
    assert first_elapsed >= DELAY_SECONDS
    assert retry_elapsed < DELAY_SECONDS / 2
    assert appointment_count == 1
    outcomes = [
        event["outcome"]
        for event in events.json()["events"]
        if event["event_type"] == "response_outcome"
    ]
    assert outcomes == ["created_then_response_delayed", "duplicate_returned"]
    assert {event["idempotency_key"] for event in events.json()["events"]} == {CANONICAL_KEY}
    _assert_secrets_omitted(first)
    _assert_secrets_omitted(second)
