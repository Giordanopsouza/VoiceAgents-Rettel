import hashlib
import hmac
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import AppointmentSlot
from app.retell_auth import RETELL_SIGNATURE_HEADER
from app.retell_availability import (
    speakable_date,
    speakable_time,
    unwrap_availability_request,
)
from app.settings import Settings

TEST_API_KEY = "test-retell-api-key"
OTHER_API_KEY = "other-retell-api-key"
PATH = "/retell/check_availability"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "retell" / "check_availability.json"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiJ9.secret-access-token"
TRANSCRIPT = "Agent: Hi there.\nUser: Can I come next Tuesday?"
MONDAY_AGENT_SLOTS = [
    {"id": "SLOT-002", "time_label": "2:30 PM"},
    {"id": "SLOT-003", "time_label": "3:00 PM"},
]
TUESDAY_AGENT_SLOTS = [
    {"id": "SLOT-005", "time_label": "2:00 PM"},
    {"id": "SLOT-007", "time_label": "3:00 PM"},
    {"id": "SLOT-008", "time_label": "3:30 PM"},
]


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


def _wrapped(*, date: object | None = "2026-09-14", call_id: str = "call_abc") -> dict:
    args: dict = {}
    if date is not None:
        args["date"] = date
    return {
        "name": "check_availability",
        "args": args,
        "call": {
            "call_id": call_id,
            "call_type": "web_call",
            "access_token": ACCESS_TOKEN,
            "transcript": TRANSCRIPT,
        },
    }


def _client(tmp_path: Path, *, retell_api_key: str = TEST_API_KEY):
    settings = Settings(
        database_path=tmp_path / "calendar.sqlite",
        retell_api_key=retell_api_key,
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
    assert "next Tuesday" not in text
    if signature:
        assert signature not in text
        digest = signature.split("d=", 1)[-1]
        assert digest not in text


def test_tool_schema_requires_iso_date_argument():
    schema = _schema()
    parameters = schema["parameters"]

    assert schema["name"] == "check_availability"
    assert schema["http"]["method"] == "POST"
    assert schema["http"]["path"] == PATH
    assert schema["http"]["url"] == "https://<PUBLIC_HOST>/retell/check_availability"
    assert schema["http"]["timeout_ms"] == 10000
    assert schema["http"]["max_retry"] == 0
    assert schema["http"]["args_at_root"] is False
    assert parameters["type"] == "object"
    assert parameters["required"] == ["date"]
    assert parameters["properties"]["date"]["type"] == "string"
    assert "YYYY-MM-DD" in parameters["properties"]["date"]["description"]
    assert "natural-language" in schema["description"]


def test_signed_wrapped_payload_returns_speakable_monday_slots(tmp_path: Path):
    payload = _wrapped(date="2026-09-14")
    body = json.dumps(payload)
    with _client(tmp_path) as client:
        response = _post(client, body, _sign(body))
        events = client.get("/api/events")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "dentist_name": "Dr. Elena Voss",
        "date": "2026-09-14",
        "date_label": "Monday, September 14, 2026",
        "slots": MONDAY_AGENT_SLOTS,
    }
    assert [event["event_type"] for event in events.json()["events"]] == [
        "receipt",
        "availability_result",
        "response_outcome",
    ]
    assert {event["call_id"] for event in events.json()["events"]} == {"call_abc"}
    _assert_secrets_omitted(response)
    _assert_secrets_omitted(events)


def test_signed_wrapped_payload_returns_speakable_tuesday_slots(tmp_path: Path):
    payload = _wrapped(date="2026-09-15", call_id="call_tue")
    body = json.dumps(payload)
    with _client(tmp_path) as client:
        response = _post(client, body, _sign(body))

    assert response.status_code == 200
    body_json = response.json()
    assert body_json["ok"] is True
    assert body_json["date_label"] == "Tuesday, September 15, 2026"
    assert body_json["slots"] == TUESDAY_AGENT_SLOTS
    _assert_secrets_omitted(response)


def test_unsigned_and_invalid_signatures_are_rejected(tmp_path: Path):
    payload = _wrapped()
    body = json.dumps(payload)
    with _client(tmp_path) as client:
        missing = _post(client, body, None)
        invalid = _post(client, body, _sign(body, api_key=OTHER_API_KEY))
        events = client.get("/api/events")

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert missing.json() == {"detail": {"message": "Unauthorized"}}
    assert invalid.json() == {"detail": {"message": "Unauthorized"}}
    assert events.json() == {"events": []}
    _assert_secrets_omitted(missing)
    _assert_secrets_omitted(invalid, _sign(body, api_key=OTHER_API_KEY))


def test_required_schema_argument_missing_returns_bounded_agent_error(tmp_path: Path):
    schema = _schema()
    payload = _wrapped(date=None)
    assert "date" in schema["parameters"]["required"]
    assert "date" not in payload["args"]
    body = json.dumps(payload)
    with _client(tmp_path) as client:
        response = _post(client, body, _sign(body))
        events = client.get("/api/events")

    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "error": "invalid_request",
        "message": "Function arguments must include date as YYYY-MM-DD.",
    }
    assert events.json() == {"events": []}
    _assert_secrets_omitted(response)


def test_unwrapped_args_only_payload_returns_bounded_agent_error(tmp_path: Path):
    payload = {"date": "2026-09-14"}
    body = json.dumps(payload)
    with _client(tmp_path) as client:
        response = _post(client, body, _sign(body))

    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "error": "invalid_request",
        "message": (
            "Request must be Retell's wrapped custom-function payload with args.date."
        ),
    }
    _assert_secrets_omitted(response)


def test_invalid_and_unsupported_dates_return_bounded_agent_errors(tmp_path: Path):
    natural = _wrapped(date="next Tuesday")
    unsupported = _wrapped(date="2026-09-16")
    with _client(tmp_path) as client:
        natural_body = json.dumps(natural)
        unsupported_body = json.dumps(unsupported)
        natural_response = _post(client, natural_body, _sign(natural_body))
        unsupported_response = _post(
            client, unsupported_body, _sign(unsupported_body)
        )
        events = client.get("/api/events")

    assert natural_response.status_code == 200
    assert natural_response.json() == {
        "ok": False,
        "error": "invalid_date",
        "message": "Date must be an ISO calendar date (YYYY-MM-DD).",
    }
    assert unsupported_response.status_code == 200
    assert unsupported_response.json() == {
        "ok": False,
        "error": "unsupported_date",
        "message": "Availability can only be queried for 2026-09-14 or 2026-09-15.",
        "available_dates": ["2026-09-14", "2026-09-15"],
    }
    assert "next Tuesday" not in natural_response.text
    assert [event["outcome"] for event in events.json()["events"]] == [
        "received",
        "invalid_date",
        "returned",
        "received",
        "unsupported_date",
        "returned",
    ]
    _assert_secrets_omitted(natural_response)
    _assert_secrets_omitted(unsupported_response)


def test_occupied_slots_are_omitted_and_empty_days_stay_bounded(tmp_path: Path):
    payload = _wrapped(date="2026-09-14")
    body = json.dumps(payload)
    with _client(tmp_path) as client:
        with client.app.state.session_factory() as session:
            for slot_id in ("SLOT-002", "SLOT-003"):
                slot = session.get(AppointmentSlot, slot_id)
                assert slot is not None
                slot.status = "occupied"
            session.commit()
        response = _post(client, body, _sign(body))

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "dentist_name": "Dr. Elena Voss",
        "date": "2026-09-14",
        "date_label": "Monday, September 14, 2026",
        "slots": [],
        "message": (
            "No open appointments on Monday, September 14, 2026. "
            "Ask for 2026-09-14 or 2026-09-15."
        ),
    }
    _assert_secrets_omitted(response)


def test_dashboard_availability_is_unchanged_iso_lookup(tmp_path: Path):
    with _client(tmp_path) as client:
        response = client.get("/api/availability", params={"date": "2026-09-14"})
        events = client.get("/api/events")

    assert response.status_code == 200
    assert response.json()["slots"][0]["starts_at"] == "2026-09-14T14:30:00Z"
    assert events.json() == {"events": []}


def test_unwrap_reads_wrapped_args_and_call_id_without_parsing_language():
    payload = _wrapped(date="next Tuesday", call_id="call_xyz")
    query_date, call_id = unwrap_availability_request(payload)

    assert query_date == "next Tuesday"
    assert call_id == "call_xyz"


def test_speakable_labels_use_demo_clock_values():
    assert speakable_date("2026-09-14") == "Monday, September 14, 2026"
    assert speakable_time("2026-09-14T14:00:00Z") == "2:00 PM"
    assert speakable_time("2026-09-14T14:30:00Z") == "2:30 PM"
    assert speakable_time("2026-09-15T15:30:00Z") == "3:30 PM"
