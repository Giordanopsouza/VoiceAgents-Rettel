import json
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib import error

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from app.web_calls import DEMO_METADATA, RETELL_CREATE_WEB_CALL_URL

TEST_API_KEY = "test-retell-api-key"
TEST_AGENT_ID = "agent_test_123"
PATH = "/api/web-calls"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiJ9.secret-access-token"
CALL_ID = "call_demo_abc123"
FORBIDDEN_KEYS = {
    "api_key",
    "retell_api_key",
    "signature",
    "x-retell-signature",
    "agent_id",
    "agent_name",
    "agent_version",
    "transcript",
    "metadata",
    "authorization",
}


def _client(
    tmp_path: Path,
    *,
    live_demo_enabled: bool = True,
    retell_api_key: str = TEST_API_KEY,
    retell_agent_id: str = TEST_AGENT_ID,
):
    settings = Settings(
        database_path=tmp_path / "calendar.sqlite",
        live_demo_enabled=live_demo_enabled,
        retell_api_key=retell_api_key,
        retell_agent_id=retell_agent_id,
        _env_file=None,
    )
    return TestClient(create_app(settings))


def _retell_success_response() -> dict:
    return {
        "call_type": "web_call",
        "access_token": ACCESS_TOKEN,
        "call_id": CALL_ID,
        "agent_id": TEST_AGENT_ID,
        "agent_version": 1,
        "call_status": "registered",
        "metadata": DEMO_METADATA,
        "transcript": "Agent: Hi there.",
    }


def _http_error(status: int, body: str = "") -> error.HTTPError:
    return error.HTTPError(
        RETELL_CREATE_WEB_CALL_URL,
        status,
        "error",
        {},
        None,
    )


def test_create_web_call_returns_browser_session_fields(tmp_path: Path):
    with patch(
        "app.web_calls._call_retell_create_web_call",
        return_value=_retell_success_response(),
    ):
        with _client(tmp_path) as client:
            response = client.post(PATH)

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "access_token": ACCESS_TOKEN,
        "call_id": CALL_ID,
    }
    assert set(body) == {"access_token", "call_id"}


def test_create_web_call_uses_configured_agent_and_demo_metadata(tmp_path: Path):
    captured: dict[str, object] = {}

    def _capture_request(http_request, timeout):
        captured["url"] = http_request.full_url
        captured["authorization"] = http_request.headers.get("Authorization")
        captured["body"] = json.loads(http_request.data.decode("utf-8"))
        return BytesIO(json.dumps(_retell_success_response()).encode("utf-8"))

    with patch("app.web_calls.request.urlopen", side_effect=_capture_request):
        with _client(tmp_path) as client:
            client.post(PATH)

    assert captured["url"] == RETELL_CREATE_WEB_CALL_URL
    assert captured["authorization"] == f"Bearer {TEST_API_KEY}"
    assert captured["body"] == {
        "agent_id": TEST_AGENT_ID,
        "metadata": DEMO_METADATA,
    }


def test_create_web_call_is_blocked_when_live_demo_is_paused(tmp_path: Path):
    with _client(tmp_path, live_demo_enabled=False) as client:
        response = client.post(PATH)

    assert response.status_code == 403
    assert response.json() == {
        "detail": {
            "error": "live_demo_paused",
            "message": (
                "Live web calls are unavailable while the public demo is paused."
            ),
        }
    }


def test_create_web_call_requires_retell_api_key(tmp_path: Path):
    with _client(tmp_path, retell_api_key="") as client:
        response = client.post(PATH)

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "retell_not_configured"


def test_create_web_call_requires_retell_agent_id(tmp_path: Path):
    with _client(tmp_path, retell_agent_id="") as client:
        response = client.post(PATH)

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "retell_agent_not_configured"


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, "retell_not_configured"),
        (403, "retell_not_configured"),
        (429, "retell_rate_limited"),
        (400, "retell_rejected"),
        (422, "retell_rejected"),
        (500, "retell_unavailable"),
    ],
)
def test_create_web_call_maps_retell_failures_to_bounded_errors(
    tmp_path: Path,
    status: int,
    error: str,
):
    with patch(
        "app.web_calls.request.urlopen",
        side_effect=_http_error(status),
    ):
        with _client(tmp_path) as client:
            response = client.post(PATH)

    body = response.json()
    assert body["detail"]["error"] == error
    assert TEST_API_KEY not in json.dumps(body)
    assert ACCESS_TOKEN not in json.dumps(body)


def test_create_web_call_maps_network_failures_to_bounded_errors(tmp_path: Path):
    with patch(
        "app.web_calls.request.urlopen",
        side_effect=error.URLError("network down"),
    ):
        with _client(tmp_path) as client:
            response = client.post(PATH)

    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "retell_unavailable"


def test_create_web_call_rejects_unexpected_retell_payload(tmp_path: Path):
    with patch(
        "app.web_calls._call_retell_create_web_call",
        return_value={"call_id": CALL_ID},
    ):
        with _client(tmp_path) as client:
            response = client.post(PATH)

    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "invalid_retell_response"


def test_create_web_call_response_omits_privileged_fields(tmp_path: Path):
    with patch(
        "app.web_calls._call_retell_create_web_call",
        return_value=_retell_success_response(),
    ):
        with _client(tmp_path) as client:
            response = client.post(PATH)

    lowered = json.dumps(response.json()).lower()
    for key in FORBIDDEN_KEYS:
        assert key not in lowered
