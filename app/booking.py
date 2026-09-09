import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Appointment, AppointmentSlot, IdempotencyRecord

_INVALID_KEY_MESSAGE = "An idempotency key is required."
_INVALID_SLOT_MESSAGE = "A slot ID is required."
_INVALID_PATIENT_MESSAGE = "A fictional patient name is required."
_UNKNOWN_SLOT_MESSAGE = "The requested appointment slot was not found."
_UNAVAILABLE_SLOT_MESSAGE = "The requested appointment slot is not available."
_IDEMPOTENCY_CONFLICT_MESSAGE = (
    "This idempotency key was already used with a different booking payload."
)


class BookingError(Exception):
    """Raised for invalid, unavailable, or conflicting booking requests."""

    def __init__(self, error: str, message: str) -> None:
        super().__init__(message)
        self.error = error
        self.message = message


def book_appointment(
    session: Session,
    *,
    idempotency_key: str,
    slot_id: str,
    patient_name: str,
) -> dict:
    """Create an appointment, or return the original row for a matching retry.

    Callers supply the idempotency key. Payload hashing and slot locking stay
    in this calendar service; Retell payload unwrapping belongs in the adapter.
    """
    key = _require_text(idempotency_key, "invalid_idempotency_key", _INVALID_KEY_MESSAGE)
    slot_id = _require_text(slot_id, "invalid_slot_id", _INVALID_SLOT_MESSAGE)
    patient_name = _require_text(
        patient_name, "invalid_patient_name", _INVALID_PATIENT_MESSAGE
    )
    fingerprint = _request_fingerprint(slot_id, patient_name)

    try:
        result = _create_or_replay(session, key, fingerprint, slot_id, patient_name)
        session.commit()
        return result
    except BookingError:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        return _recover_from_constraint(session, key, fingerprint)


def _create_or_replay(
    session: Session,
    key: str,
    fingerprint: str,
    slot_id: str,
    patient_name: str,
) -> dict:
    existing = session.get(IdempotencyRecord, key)
    if existing is not None:
        return _replay_or_conflict(session, existing, fingerprint)

    slot = session.get(AppointmentSlot, slot_id)
    if slot is None:
        raise BookingError("unknown_slot", _UNKNOWN_SLOT_MESSAGE)
    if slot.status != "available":
        raise BookingError("slot_unavailable", _UNAVAILABLE_SLOT_MESSAGE)

    created_at = _utc_now()
    appointment = Appointment(
        id=_next_appointment_id(session),
        slot_id=slot.id,
        patient_name=patient_name,
        status="active",
        created_at=created_at,
    )
    session.add(appointment)
    session.add(
        IdempotencyRecord(
            key=key,
            request_fingerprint=fingerprint,
            appointment_id=appointment.id,
            created_at=created_at,
        )
    )
    slot.status = "occupied"
    session.flush()
    return _payload(appointment, replayed=False)


def _recover_from_constraint(session: Session, key: str, fingerprint: str) -> dict:
    existing = session.get(IdempotencyRecord, key)
    if existing is not None:
        return _replay_or_conflict(session, existing, fingerprint)
    raise BookingError("slot_unavailable", _UNAVAILABLE_SLOT_MESSAGE)


def _replay_or_conflict(
    session: Session, record: IdempotencyRecord, fingerprint: str
) -> dict:
    if record.request_fingerprint != fingerprint:
        raise BookingError("idempotency_conflict", _IDEMPOTENCY_CONFLICT_MESSAGE)
    appointment = session.get(Appointment, record.appointment_id)
    if appointment is None:
        raise BookingError("idempotency_conflict", _IDEMPOTENCY_CONFLICT_MESSAGE)
    return _payload(appointment, replayed=True)


def _payload(appointment: Appointment, *, replayed: bool) -> dict:
    return {
        "appointment": {
            "id": appointment.id,
            "slot_id": appointment.slot_id,
            "patient_name": appointment.patient_name,
            "status": appointment.status,
            "created_at": appointment.created_at,
        },
        "replayed": replayed,
    }


def _next_appointment_id(session: Session) -> str:
    count = session.scalar(select(func.count()).select_from(Appointment)) or 0
    return f"APT-{count + 1:03d}"


def _request_fingerprint(slot_id: str, patient_name: str) -> str:
    canonical = json.dumps(
        {"patient_name": patient_name, "slot_id": slot_id},
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _require_text(value: object, error: str, message: str) -> str:
    if not isinstance(value, str):
        raise BookingError(error, message)
    stripped = value.strip()
    if not stripped:
        raise BookingError(error, message)
    return stripped


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
