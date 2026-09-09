import hashlib
import json
from typing import Annotated, NamedTuple

from fastapi import APIRouter, Depends, Request

from app.booking import BookingError
from app.events import record_booking_attempt
from app.models import AppointmentSlot
from app.retell_auth import verified_retell_payload
from app.retell_availability import speakable_date, speakable_time
from app.seed import DENTIST_NAME

_UNWRAPPED_MESSAGE = (
    "Request must be Retell's wrapped custom-function payload with "
    "args.slot_id, args.patient_name, args.dentist_name, and args.confirmed."
)
_MISSING_ARGS_MESSAGE = (
    "Function arguments must include slot_id, patient_name, dentist_name, "
    "and confirmed."
)
_MISSING_CALL_ID_MESSAGE = "Request must include call.call_id."
_CONFIRMATION_MESSAGE = (
    "Booking requires confirmed=true after the caller explicitly confirms "
    "dentist, date, and time."
)
_INVALID_SLOT_MESSAGE = "Function arguments must include slot_id as a slot ID."
_INVALID_PATIENT_MESSAGE = "Function arguments must include a fictional patient name."
_INVALID_DENTIST_MESSAGE = "Function arguments must include dentist_name."
_UNKNOWN_DENTIST_MESSAGE = "This clinic only books with Dr. Elena Voss."
_CREATED_MESSAGE = (
    "Appointment {appointment_id} is booked for {date_label} at {time_label}. "
    "Tell the caller once. Do not ask them to confirm again."
)
_REPLAYED_MESSAGE = (
    "Appointment {appointment_id} was already booked on the first attempt "
    "for {date_label} at {time_label}. Tell the caller once. "
    "Do not ask them to confirm again."
)
_REQUIRED_ARGS = ("slot_id", "patient_name", "dentist_name", "confirmed")
_SAFE_KEY_PREFIX = "bk_"


class RetellBookingError(Exception):
    """Raised when the Retell payload cannot be mapped onto booking."""

    def __init__(self, error: str, message: str) -> None:
        super().__init__(message)
        self.error = error
        self.message = message


class BookingRequest(NamedTuple):
    call_id: str
    slot_id: str
    dentist_name: str
    patient_name: str


def unwrap_booking_request(payload: dict) -> BookingRequest:
    """Return canonical booking fields from Retell's wrapped custom-function body.

    Confirmation and identity checks stay here. Calendar creation stays in
    the booking service.
    """
    args = payload.get("args")
    if not isinstance(args, dict):
        raise RetellBookingError("invalid_request", _UNWRAPPED_MESSAGE)
    if any(name not in args for name in _REQUIRED_ARGS):
        raise RetellBookingError("invalid_request", _MISSING_ARGS_MESSAGE)
    if args["confirmed"] is not True:
        raise RetellBookingError("confirmation_required", _CONFIRMATION_MESSAGE)

    slot_id = _require_text(args["slot_id"], "invalid_slot_id", _INVALID_SLOT_MESSAGE)
    patient_name = _require_text(
        args["patient_name"], "invalid_patient_name", _INVALID_PATIENT_MESSAGE
    )
    dentist_name = _require_text(
        args["dentist_name"], "invalid_dentist", _INVALID_DENTIST_MESSAGE
    )
    if _canonicalize(dentist_name) != _canonicalize(DENTIST_NAME):
        raise RetellBookingError("invalid_dentist", _UNKNOWN_DENTIST_MESSAGE)

    call = payload.get("call")
    call_id = call.get("call_id") if isinstance(call, dict) else None
    if not isinstance(call_id, str) or not call_id.strip():
        raise RetellBookingError("invalid_request", _MISSING_CALL_ID_MESSAGE)

    return BookingRequest(
        call_id=call_id.strip(),
        slot_id=slot_id,
        dentist_name=DENTIST_NAME,
        patient_name=_canonicalize(patient_name),
    )


def derive_idempotency_key(
    *,
    call_id: str,
    slot_id: str,
    dentist_name: str,
    patient_name: str,
) -> str:
    """Hash canonical booking identity into a display-safe idempotency key."""
    canonical = json.dumps(
        {
            "call_id": call_id.strip(),
            "dentist_name": _canonicalize(dentist_name),
            "patient_name": _canonicalize(patient_name),
            "slot_id": slot_id.strip(),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{_SAFE_KEY_PREFIX}{digest}"


def agent_booking_payload(result: dict, slot: AppointmentSlot) -> dict:
    """Shape a booking result into concise JSON the voice agent can speak."""
    appointment_id = result["appointment"]["id"]
    date_iso = slot.starts_at[:10]
    date_label = speakable_date(date_iso)
    time_label = speakable_time(slot.starts_at)
    replayed = result["replayed"]
    template = _REPLAYED_MESSAGE if replayed else _CREATED_MESSAGE
    return {
        "ok": True,
        "replayed": replayed,
        "appointment_id": appointment_id,
        "slot_id": slot.id,
        "dentist_name": slot.dentist_name,
        "date": date_iso,
        "date_label": date_label,
        "time_label": time_label,
        "message": template.format(
            appointment_id=appointment_id,
            date_label=date_label,
            time_label=time_label,
        ),
    }


def book_appointment(
    request: Request,
    payload: Annotated[dict, Depends(verified_retell_payload)],
) -> dict:
    try:
        booking = unwrap_booking_request(payload)
    except RetellBookingError as exc:
        return _error_payload(exc.error, exc.message)

    idempotency_key = derive_idempotency_key(
        call_id=booking.call_id,
        slot_id=booking.slot_id,
        dentist_name=booking.dentist_name,
        patient_name=booking.patient_name,
    )
    try:
        with request.app.state.session_factory() as session:
            result = record_booking_attempt(
                session,
                call_id=booking.call_id,
                idempotency_key=idempotency_key,
                slot_id=booking.slot_id,
                patient_name=booking.patient_name,
                failure_lab=request.app.state.failure_lab,
            )
            slot = session.get(AppointmentSlot, booking.slot_id)
    except BookingError as exc:
        return _error_payload(exc.error, exc.message)
    if slot is None:
        return _error_payload("unknown_slot", "The requested appointment slot was not found.")
    return agent_booking_payload(result, slot)


def register_retell_booking(router: APIRouter) -> None:
    """Attach the signed booking tool once onto the shared Retell router."""
    if any(getattr(route, "path", None) == "/book_appointment" for route in router.routes):
        return
    router.add_api_route(
        "/book_appointment",
        book_appointment,
        methods=["POST"],
    )


def _canonicalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def _require_text(value: object, error: str, message: str) -> str:
    if not isinstance(value, str):
        raise RetellBookingError(error, message)
    stripped = value.strip()
    if not stripped:
        raise RetellBookingError(error, message)
    return stripped


def _error_payload(error: str, message: str) -> dict:
    return {"ok": False, "error": error, "message": message}
