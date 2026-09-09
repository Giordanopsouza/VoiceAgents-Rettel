from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.availability import AvailabilityQueryError
from app.events import record_availability_attempt
from app.retell_auth import verified_retell_payload
from app.seed import DEMO_DATES

_UNWRAPPED_MESSAGE = (
    "Request must be Retell's wrapped custom-function payload with args.date."
)
_MISSING_DATE_MESSAGE = "Function arguments must include date as YYYY-MM-DD."
_NO_SLOTS_MESSAGE = (
    "No open appointments on {date_label}. Ask for 2026-09-14 or 2026-09-15."
)


class RetellAvailabilityError(Exception):
    """Raised when the Retell payload cannot be mapped onto availability lookup."""

    def __init__(self, error: str, message: str) -> None:
        super().__init__(message)
        self.error = error
        self.message = message


def unwrap_availability_request(payload: dict) -> tuple[object, object]:
    """Return `(query_date, call_id)` from Retell's wrapped custom-function body.

    Natural-language dates are not parsed here. The calendar service validates
    the `date` argument after this adapter extracts it from `args`.
    """
    args = payload.get("args")
    if not isinstance(args, dict):
        raise RetellAvailabilityError("invalid_request", _UNWRAPPED_MESSAGE)
    if "date" not in args:
        raise RetellAvailabilityError("invalid_request", _MISSING_DATE_MESSAGE)
    call = payload.get("call")
    call_id = call.get("call_id") if isinstance(call, dict) else None
    return args["date"], call_id


def agent_availability_payload(calendar_result: dict) -> dict:
    """Shape calendar slots into concise JSON the voice agent can speak."""
    date_iso = calendar_result["date"]
    date_label = speakable_date(date_iso)
    slots = [
        {
            "id": slot["id"],
            "time_label": speakable_time(slot["starts_at"]),
        }
        for slot in calendar_result["slots"]
    ]
    payload = {
        "ok": True,
        "dentist_name": calendar_result["dentist_name"],
        "date": date_iso,
        "date_label": date_label,
        "slots": slots,
    }
    if not slots:
        payload["message"] = _NO_SLOTS_MESSAGE.format(date_label=date_label)
    return payload


def speakable_date(iso_date: str) -> str:
    day = date.fromisoformat(iso_date)
    return f"{day.strftime('%A, %B')} {day.day}, {day.year}"


def speakable_time(iso_timestamp: str) -> str:
    moment = datetime.strptime(iso_timestamp, "%Y-%m-%dT%H:%M:%SZ")
    hour12 = moment.hour % 12 or 12
    suffix = "AM" if moment.hour < 12 else "PM"
    return f"{hour12}:{moment.minute:02d} {suffix}"


def _error_payload(error: str, message: str) -> dict:
    payload = {"ok": False, "error": error, "message": message}
    if error == "unsupported_date":
        payload["available_dates"] = list(DEMO_DATES)
    return payload


def check_availability(
    request: Request,
    payload: Annotated[dict, Depends(verified_retell_payload)],
) -> dict:
    try:
        query_date, call_id = unwrap_availability_request(payload)
    except RetellAvailabilityError as exc:
        return _error_payload(exc.error, exc.message)
    try:
        with request.app.state.session_factory() as session:
            result = record_availability_attempt(
                session, call_id=call_id, query_date=query_date
            )
    except AvailabilityQueryError as exc:
        return _error_payload(exc.error, exc.message)
    return agent_availability_payload(result)


def register_retell_availability(router: APIRouter) -> None:
    """Attach the signed availability tool once onto the shared Retell router."""
    if any(
        getattr(route, "path", None) == "/check_availability"
        for route in router.routes
    ):
        return
    router.add_api_route(
        "/check_availability",
        check_availability,
        methods=["POST"],
    )
