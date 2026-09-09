import hashlib
import hmac
import json
import re
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.settings import Settings

RETELL_SIGNATURE_HEADER = "X-Retell-Signature"
REPLAY_WINDOW_MS = 5 * 60 * 1000
_SIGNATURE_PATTERN = re.compile(r"^v=(\d+),d=([0-9a-f]{64})$")
_UNAUTHORIZED = {"message": "Unauthorized"}
_INVALID_JSON = {"message": "Invalid JSON"}


def verify_retell_signature(
    raw_body: str,
    signature: str | None,
    api_key: str,
    *,
    now_ms: int | None = None,
) -> bool:
    """Return True when `signature` is a current HMAC of the exact raw body.

    Matches Retell's documented scheme: `v={unix_ms},d={hex}` is HMAC-SHA256
    of `raw_body + timestamp` keyed with the Retell API key. An empty API key
    never verifies, so local tests must supply a key instead of skipping checks.
    """
    if not api_key or not signature:
        return False
    match = _SIGNATURE_PATTERN.fullmatch(signature)
    if match is None:
        return False
    timestamp_ms = int(match.group(1))
    digest = match.group(2)
    now = int(time.time() * 1000) if now_ms is None else now_ms
    if abs(now - timestamp_ms) > REPLAY_WINDOW_MS:
        return False
    expected = hmac.new(
        api_key.encode("utf-8"),
        f"{raw_body}{timestamp_ms}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, digest)


async def require_retell_signature(request: Request) -> str:
    """Reject the request unless `X-Retell-Signature` matches the raw body."""
    raw_body = await request.body()
    try:
        raw_text = raw_body.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED) from None
    settings: Settings = request.app.state.settings
    signature = request.headers.get(RETELL_SIGNATURE_HEADER)
    if not verify_retell_signature(raw_text, signature, settings.retell_api_key):
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED)
    return raw_text


async def verified_retell_payload(
    raw_text: Annotated[str, Depends(require_retell_signature)],
) -> dict:
    """Parse JSON only after the Retell signature has been verified."""
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail=_INVALID_JSON) from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail=_INVALID_JSON)
    return payload


retell_router = APIRouter(
    prefix="/retell",
    tags=["retell"],
    dependencies=[Depends(require_retell_signature)],
)
