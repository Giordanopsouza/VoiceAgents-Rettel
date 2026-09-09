import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.availability import AvailabilityQueryError, list_available_slots
from app.booking import BookingError, book_appointment
from app.failure_lab import FailureLab
from app.models import RequestEvent

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_BLOCKED_IDENTIFIER_TOKENS = (
    "api_key",
    "apikey",
    "signature",
    "access_token",
    "bearer",
    "transcript",
    "sk-",
    "secret",
    "password",
    "authorization",
)
_BOOKING_ERROR_EVENTS = {
    "idempotency_conflict": ("conflict", "rejected", "conflict_returned"),
    "slot_unavailable": ("new_key", "rejected", "slot_rejected"),
    "unknown_slot": ("new_key", "rejected", "slot_rejected"),
}


def record_booking_attempt(
    session: Session,
    *,
    call_id: object,
    idempotency_key: object,
    slot_id: object,
    patient_name: object,
    failure_lab: FailureLab | None = None,
) -> dict:
    """Book an appointment and persist the sanitized attempt timeline.

    Calendar creation stays in `book_appointment`. This wrapper records
    receipt, idempotency decision, appointment result, and response outcome
    so the dashboard can explain retries without storing sensitive payloads.

    When Failure Lab is enabled, a first successful create records
    `created_then_response_delayed` and then sleeps. The appointment and
    events are committed before that wait so a concurrent retry can return
    `duplicate_returned` without blocking on the delayed response.
    """
    safe_call_id = _safe_correlation_id(call_id)
    safe_key = _safe_correlation_id(idempotency_key)
    attempt_number = _next_attempt_number(session, idempotency_key=safe_key)
    _persist_event(
        session,
        attempt_number=attempt_number,
        event_type="receipt",
        outcome="received",
        call_id=safe_call_id,
        idempotency_key=safe_key,
    )
    try:
        result = book_appointment(
            session,
            idempotency_key=idempotency_key,
            slot_id=slot_id,
            patient_name=patient_name,
        )
    except BookingError as exc:
        decision, appointment_outcome, response_outcome = _booking_error_outcomes(
            exc.error
        )
        _persist_booking_followup(
            session,
            attempt_number=attempt_number,
            call_id=safe_call_id,
            idempotency_key=safe_key,
            decision=decision,
            appointment_outcome=appointment_outcome,
            response_outcome=response_outcome,
        )
        raise

    appointment_id = result["appointment"]["id"]
    replayed = result["replayed"]
    delayed = False
    if failure_lab is not None and not replayed:
        delay_key = safe_key or _delay_key(idempotency_key)
        delayed = failure_lab.claim_delay(delay_key)
    response_outcome = _booking_response_outcome(replayed=replayed, delayed=delayed)
    _persist_booking_followup(
        session,
        attempt_number=attempt_number,
        call_id=safe_call_id,
        idempotency_key=safe_key,
        appointment_id=appointment_id,
        decision="existing_key" if replayed else "new_key",
        appointment_outcome="replayed" if replayed else "created",
        response_outcome=response_outcome,
    )
    if failure_lab is not None:
        failure_lab.wait_if_delayed(delayed)
    return result


def record_availability_attempt(
    session: Session,
    *,
    call_id: object,
    query_date: object,
) -> dict:
    """Look up open slots and persist a sanitized availability timeline."""
    safe_call_id = _safe_correlation_id(call_id)
    attempt_number = _next_attempt_number(
        session, call_id=safe_call_id, idempotency_key=None
    )
    _persist_event(
        session,
        attempt_number=attempt_number,
        event_type="receipt",
        outcome="received",
        call_id=safe_call_id,
    )
    try:
        result = list_available_slots(session, query_date)
    except AvailabilityQueryError as exc:
        _persist_availability_followup(
            session,
            attempt_number=attempt_number,
            call_id=safe_call_id,
            result_outcome=exc.error,
        )
        raise

    _persist_availability_followup(
        session,
        attempt_number=attempt_number,
        call_id=safe_call_id,
        result_outcome="slots_returned",
    )
    return result


def list_request_events(session: Session) -> list[dict]:
    """Return the current demo session's events in chronological order."""
    rows = session.scalars(
        select(RequestEvent).order_by(RequestEvent.created_at, RequestEvent.id)
    ).all()
    return [_public_event(row) for row in rows]


def _persist_booking_followup(
    session: Session,
    *,
    attempt_number: int,
    call_id: str | None,
    idempotency_key: str | None,
    decision: str,
    appointment_outcome: str,
    response_outcome: str,
    appointment_id: str | None = None,
) -> None:
    for event_type, outcome in (
        ("idempotency_decision", decision),
        ("appointment_result", appointment_outcome),
        ("response_outcome", response_outcome),
    ):
        _persist_event(
            session,
            attempt_number=attempt_number,
            event_type=event_type,
            outcome=outcome,
            appointment_id=appointment_id,
            call_id=call_id,
            idempotency_key=idempotency_key,
            commit=False,
        )
    session.commit()


def _persist_availability_followup(
    session: Session,
    *,
    attempt_number: int,
    call_id: str | None,
    result_outcome: str,
) -> None:
    for event_type, outcome in (
        ("availability_result", result_outcome),
        ("response_outcome", "returned"),
    ):
        _persist_event(
            session,
            attempt_number=attempt_number,
            event_type=event_type,
            outcome=outcome,
            call_id=call_id,
            commit=False,
        )
    session.commit()


def _persist_event(
    session: Session,
    *,
    attempt_number: int,
    event_type: str,
    outcome: str,
    appointment_id: str | None = None,
    idempotency_key: str | None = None,
    call_id: str | None = None,
    commit: bool = True,
) -> None:
    session.add(
        RequestEvent(
            created_at=_utc_now(),
            attempt_number=attempt_number,
            event_type=event_type,
            outcome=outcome,
            appointment_id=appointment_id,
            idempotency_key=idempotency_key,
            call_id=call_id,
        )
    )
    if commit:
        session.commit()


def _public_event(row: RequestEvent) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "attempt_number": row.attempt_number,
        "event_type": row.event_type,
        "outcome": row.outcome,
        "appointment_id": row.appointment_id,
        "idempotency_key": row.idempotency_key,
        "call_id": row.call_id,
    }


def _next_attempt_number(
    session: Session,
    *,
    idempotency_key: str | None = None,
    call_id: str | None = None,
) -> int:
    query = select(func.count()).select_from(RequestEvent).where(
        RequestEvent.event_type == "receipt"
    )
    if idempotency_key is not None:
        query = query.where(RequestEvent.idempotency_key == idempotency_key)
    else:
        query = query.where(
            RequestEvent.call_id == call_id,
            RequestEvent.idempotency_key.is_(None),
        )
    return (session.scalar(query) or 0) + 1


def _booking_error_outcomes(error: str) -> tuple[str, str, str]:
    return _BOOKING_ERROR_EVENTS.get(
        error, ("invalid", "rejected", "invalid_request")
    )


def _booking_response_outcome(*, replayed: bool, delayed: bool) -> str:
    if delayed:
        return "created_then_response_delayed"
    if replayed:
        return "duplicate_returned"
    return "created_returned"


def _delay_key(idempotency_key: object) -> str | None:
    if not isinstance(idempotency_key, str):
        return None
    stripped = idempotency_key.strip()
    return stripped or None


def _safe_correlation_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not _SAFE_IDENTIFIER.fullmatch(stripped):
        return None
    lowered = stripped.lower()
    if any(token in lowered for token in _BLOCKED_IDENTIFIER_TOKENS):
        return None
    return stripped


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
