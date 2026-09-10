import hashlib
import hmac
import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.testclient import TestClient

from app.booking import book_appointment
from app.main import create_app
from app.retell_auth import (
    RETELL_SIGNATURE_HEADER,
    REPLAY_WINDOW_MS,
    require_retell_signature,
    retell_router,
    verified_retell_payload,
    verify_retell_signature,
)
from app.settings import Settings

TEST_API_KEY = "test-retell-api-key"
OTHER_API_KEY = "other-retell-api-key"
PROBE_PATH = "/retell/probe"
ROUTER_PROBE_PATH = "/retell-boundary/probe"
BOOK_PATH = "/retell/probe-book"
PAYLOAD = {"name": "check_availability", "args": {"date": "2026-09-14"}}
SPACED_BODY = '{"name": "check_availability", "args": {"date": "2026-09-14"}}'
COMPACT_BODY = '{"name":"check_availability","args":{"date":"2026-09-14"}}'


def _sign(body: str, api_key: str = TEST_API_KEY, timestamp_ms: int | None = None) -> str:
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    digest = hmac.new(
        api_key.encode("utf-8"),
        f"{body}{timestamp_ms}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"v={timestamp_ms},d={digest}"


def _client(tmp_path: Path, *, retell_api_key: str = TEST_API_KEY):
    settings = Settings(
        database_path=tmp_path / "calendar.sqlite",
        retell_api_key=retell_api_key,
        _env_file=None,
    )
    application = create_app(settings)
    handled: list[dict] = []

    @application.post(PROBE_PATH)
    async def probe(payload: dict = Depends(verified_retell_payload)) -> dict:
        handled.append(payload)
        return {"received": payload}

    protected = APIRouter(
        prefix="/retell-boundary",
        dependencies=list(retell_router.dependencies),
    )

    @protected.post("/probe")
    async def router_probe() -> dict:
        handled.append({"via": "router"})
        return {"ok": True}

    application.include_router(protected)

    @application.post(BOOK_PATH)
    async def probe_book(
        request: Request,
        payload: dict = Depends(verified_retell_payload),
    ) -> dict:
        handled.append(payload)
        with request.app.state.session_factory() as session:
            return book_appointment(
                session,
                idempotency_key="probe:booking",
                slot_id="SLOT-002",
                patient_name="Jordan Hale",
            )

    client = TestClient(application)
    client.handled = handled
    return client


def _post(client: TestClient, path: str, body: str, signature: str | None):
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers[RETELL_SIGNATURE_HEADER] = signature
    return client.post(path, content=body, headers=headers)


def _assert_secrets_omitted(response, signature: str | None = None) -> None:
    text = response.text
    assert TEST_API_KEY not in text
    assert OTHER_API_KEY not in text
    assert "retell_api_key" not in text.lower()
    if signature:
        assert signature not in text
        digest = signature.split("d=", 1)[-1]
        assert digest not in text


def test_valid_signature_parses_payload_after_verification(tmp_path: Path):
    body = json.dumps(PAYLOAD, separators=(",", ":"))
    with _client(tmp_path) as client:
        response = _post(client, PROBE_PATH, body, _sign(body))

    assert response.status_code == 200
    assert response.json() == {"received": PAYLOAD}
    assert client.handled == [PAYLOAD]
    _assert_secrets_omitted(response)


def test_missing_signature_is_unauthorized_and_does_not_parse(tmp_path: Path):
    body = json.dumps(PAYLOAD)
    with _client(tmp_path) as client:
        response = _post(client, PROBE_PATH, body, None)

    assert response.status_code == 401
    assert response.json() == {"detail": {"message": "Unauthorized"}}
    assert client.handled == []
    _assert_secrets_omitted(response)


def test_invalid_signature_is_unauthorized(tmp_path: Path):
    body = json.dumps(PAYLOAD)
    signature = _sign(body, api_key=OTHER_API_KEY)
    with _client(tmp_path) as client:
        response = _post(client, PROBE_PATH, body, signature)

    assert response.status_code == 401
    assert response.json() == {"detail": {"message": "Unauthorized"}}
    assert client.handled == []
    _assert_secrets_omitted(response, signature)


def test_tampered_body_is_unauthorized_even_when_json_is_equivalent(tmp_path: Path):
    signature = _sign(SPACED_BODY)
    with _client(tmp_path) as client:
        response = _post(client, PROBE_PATH, COMPACT_BODY, signature)

    assert json.loads(SPACED_BODY) == json.loads(COMPACT_BODY)
    assert response.status_code == 401
    assert client.handled == []
    _assert_secrets_omitted(response, signature)


def test_expired_and_future_signatures_are_unauthorized(tmp_path: Path):
    body = json.dumps(PAYLOAD)
    now = int(time.time() * 1000)
    expired = _sign(body, timestamp_ms=now - 2 * REPLAY_WINDOW_MS)
    too_new = _sign(body, timestamp_ms=now + 2 * REPLAY_WINDOW_MS)
    with _client(tmp_path) as client:
        expired_response = _post(client, PROBE_PATH, body, expired)
        future_response = _post(client, PROBE_PATH, body, too_new)

    assert expired_response.status_code == 401
    assert future_response.status_code == 401
    assert client.handled == []
    _assert_secrets_omitted(expired_response, expired)
    _assert_secrets_omitted(future_response, too_new)


def test_invalid_json_is_rejected_only_after_a_valid_signature(tmp_path: Path):
    raw = '{"name":'
    with _client(tmp_path) as client:
        unsigned = _post(client, PROBE_PATH, raw, "not-a-signature")
        signed = _post(client, PROBE_PATH, raw, _sign(raw))

    assert unsigned.status_code == 401
    assert unsigned.json() == {"detail": {"message": "Unauthorized"}}
    assert signed.status_code == 400
    assert signed.json() == {"detail": {"message": "Invalid JSON"}}
    assert client.handled == []
    _assert_secrets_omitted(unsigned, "not-a-signature")
    _assert_secrets_omitted(signed)


def test_empty_api_key_never_accepts_a_request(tmp_path: Path):
    body = json.dumps(PAYLOAD)
    signature = _sign(body, api_key="")
    with _client(tmp_path, retell_api_key="") as client:
        response = _post(client, PROBE_PATH, body, signature)

    assert response.status_code == 401
    assert client.handled == []
    _assert_secrets_omitted(response)


def test_invalid_signature_cannot_mutate_calendar_state(tmp_path: Path):
    body = json.dumps(PAYLOAD)
    signature = _sign(body, api_key=OTHER_API_KEY)
    with _client(tmp_path) as client:
        denied = _post(client, BOOK_PATH, body, signature)
        events = client.get("/api/events")
        availability = client.get("/api/availability", params={"date": "2026-09-14"})

    assert denied.status_code == 401
    assert client.handled == []
    assert events.json()["events"] == []
    assert "SLOT-002" in {slot["id"] for slot in availability.json()["slots"]}
    _assert_secrets_omitted(denied, signature)


def test_retell_router_requires_signature_before_any_tool_route(tmp_path: Path):
    body = json.dumps(PAYLOAD)
    assert any(
        getattr(dep, "dependency", None) is require_retell_signature
        for dep in retell_router.dependencies
    )
    with _client(tmp_path) as client:
        denied = _post(client, ROUTER_PROBE_PATH, body, None)
        allowed = _post(client, ROUTER_PROBE_PATH, body, _sign(body))

    assert denied.status_code == 401
    assert denied.json() == {"detail": {"message": "Unauthorized"}}
    assert allowed.status_code == 200
    assert allowed.json() == {"ok": True}
    assert client.handled == [{"via": "router"}]
    _assert_secrets_omitted(denied)
    _assert_secrets_omitted(allowed)


def test_verify_helper_accepts_current_hmac_of_exact_raw_body():
    now = 1_700_000_000_000
    signature = _sign(SPACED_BODY, timestamp_ms=now)

    assert verify_retell_signature(SPACED_BODY, signature, TEST_API_KEY, now_ms=now)
    assert not verify_retell_signature(COMPACT_BODY, signature, TEST_API_KEY, now_ms=now)
    assert not verify_retell_signature(SPACED_BODY, signature, OTHER_API_KEY, now_ms=now)
    assert not verify_retell_signature(SPACED_BODY, None, TEST_API_KEY, now_ms=now)
    assert not verify_retell_signature(SPACED_BODY, signature, "", now_ms=now)
    assert not verify_retell_signature(
        SPACED_BODY, signature, TEST_API_KEY, now_ms=now + REPLAY_WINDOW_MS + 1
    )
