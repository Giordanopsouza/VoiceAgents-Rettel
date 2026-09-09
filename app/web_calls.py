import json
from urllib import error, request

from app.settings import Settings

RETELL_CREATE_WEB_CALL_URL = "https://api.retellai.com/v2/create-web-call"
DEMO_METADATA = {
    "demo": "retell-dental-booking-lab",
    "surface": "public-dashboard",
}
_PAUSED_MESSAGE = (
    "Live web calls are unavailable while the public demo is paused."
)
_MISSING_API_KEY_MESSAGE = (
    "Live web calls are unavailable because Retell is not configured."
)
_MISSING_AGENT_MESSAGE = (
    "Live web calls are unavailable because the Retell agent is not configured."
)
_RETELL_UNAVAILABLE_MESSAGE = (
    "Retell is temporarily unavailable. Try again in a moment."
)
_INVALID_RETELL_RESPONSE_MESSAGE = (
    "Retell returned an unexpected response. Try again in a moment."
)


class WebCallError(Exception):
    """Raised when a web call cannot be created."""

    def __init__(self, error: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.error = error
        self.message = message
        self.status_code = status_code


def create_web_call(settings: Settings) -> dict[str, str]:
    """Create a Retell web call and return browser-safe session fields."""
    if not settings.live_demo_enabled:
        raise WebCallError("live_demo_paused", _PAUSED_MESSAGE, status_code=403)
    if not settings.retell_api_key:
        raise WebCallError(
            "retell_not_configured",
            _MISSING_API_KEY_MESSAGE,
            status_code=503,
        )
    if not settings.retell_agent_id:
        raise WebCallError(
            "retell_agent_not_configured",
            _MISSING_AGENT_MESSAGE,
            status_code=503,
        )

    retell_response = _call_retell_create_web_call(
        api_key=settings.retell_api_key,
        agent_id=settings.retell_agent_id,
        metadata=DEMO_METADATA,
    )
    return _public_session(retell_response)


def _public_session(retell_response: dict[str, object]) -> dict[str, str]:
    access_token = retell_response.get("access_token")
    call_id = retell_response.get("call_id")
    if not isinstance(access_token, str) or not access_token.strip():
        raise WebCallError(
            "invalid_retell_response",
            _INVALID_RETELL_RESPONSE_MESSAGE,
            status_code=502,
        )
    if not isinstance(call_id, str) or not call_id.strip():
        raise WebCallError(
            "invalid_retell_response",
            _INVALID_RETELL_RESPONSE_MESSAGE,
            status_code=502,
        )
    return {"access_token": access_token, "call_id": call_id}


def _call_retell_create_web_call(
    *,
    api_key: str,
    agent_id: str,
    metadata: dict[str, str],
) -> dict[str, object]:
    payload = json.dumps(
        {
            "agent_id": agent_id,
            "metadata": metadata,
        }
    ).encode("utf-8")
    http_request = request.Request(
        RETELL_CREATE_WEB_CALL_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(http_request, timeout=15) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        raise _retell_http_error(exc) from exc
    except error.URLError as exc:
        raise WebCallError(
            "retell_unavailable",
            _RETELL_UNAVAILABLE_MESSAGE,
            status_code=502,
        ) from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise WebCallError(
            "invalid_retell_response",
            _INVALID_RETELL_RESPONSE_MESSAGE,
            status_code=502,
        ) from exc
    if not isinstance(parsed, dict):
        raise WebCallError(
            "invalid_retell_response",
            _INVALID_RETELL_RESPONSE_MESSAGE,
            status_code=502,
        )
    return parsed


def _retell_http_error(exc: error.HTTPError) -> WebCallError:
    if exc.code in {401, 403}:
        return WebCallError(
            "retell_not_configured",
            _MISSING_API_KEY_MESSAGE,
            status_code=503,
        )
    if exc.code == 429:
        return WebCallError(
            "retell_rate_limited",
            "Retell is busy right now. Try again in a moment.",
            status_code=503,
        )
    if exc.code in {400, 404, 422}:
        return WebCallError(
            "retell_rejected",
            "Retell could not start this web call. Check the configured agent.",
            status_code=502,
        )
    return WebCallError(
        "retell_unavailable",
        _RETELL_UNAVAILABLE_MESSAGE,
        status_code=502,
    )
