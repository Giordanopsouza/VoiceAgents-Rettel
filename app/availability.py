from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppointmentSlot
from app.seed import DEMO_DATES, DENTIST_NAME, slot_to_dict

_INVALID_DATE_MESSAGE = "Date must be an ISO calendar date (YYYY-MM-DD)."
_UNSUPPORTED_DATE_MESSAGE = (
    "Availability can only be queried for 2026-09-14 or 2026-09-15."
)


class AvailabilityQueryError(Exception):
    """Raised for invalid or unsupported availability lookups."""

    def __init__(self, error: str, message: str) -> None:
        super().__init__(message)
        self.error = error
        self.message = message


def list_available_slots(session: Session, query_date: object) -> dict:
    """Return open slots for one documented demo date.

    Occupied slots are omitted. Callers pass an ISO calendar date; Retell
    payload unwrapping belongs in the adapter, not here.
    """
    day = _parse_demo_date(query_date)
    slots = session.scalars(
        select(AppointmentSlot)
        .where(
            AppointmentSlot.status == "available",
            AppointmentSlot.starts_at.startswith(day.isoformat()),
        )
        .order_by(AppointmentSlot.starts_at, AppointmentSlot.id)
    ).all()
    return {
        "date": day.isoformat(),
        "dentist_name": DENTIST_NAME,
        "slots": [slot_to_dict(slot) for slot in slots],
    }


def _parse_demo_date(value: object) -> date:
    if not isinstance(value, str) or not value:
        raise AvailabilityQueryError("invalid_date", _INVALID_DATE_MESSAGE)
    try:
        day = date.fromisoformat(value)
    except ValueError as exc:
        raise AvailabilityQueryError("invalid_date", _INVALID_DATE_MESSAGE) from exc
    if value != day.isoformat():
        raise AvailabilityQueryError("invalid_date", _INVALID_DATE_MESSAGE)
    if value not in DEMO_DATES:
        raise AvailabilityQueryError("unsupported_date", _UNSUPPORTED_DATE_MESSAGE)
    return day
