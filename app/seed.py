from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Appointment, AppointmentSlot, IdempotencyRecord, RequestEvent

DENTIST_NAME = "Dr. Elena Voss"
DEMO_DATES = ("2026-09-14", "2026-09-15")


@dataclass(frozen=True)
class SeedSlot:
    id: str
    starts_at: str
    ends_at: str
    status: str


# Canonical fictional schedule. Agent prompts in task 011 should describe
# the same dentist, dates, and clock times. Stored timestamps are UTC;
# spoken times use the same clock values (14:00 is "2:00 PM").
SEED_SLOTS: tuple[SeedSlot, ...] = (
    SeedSlot("SLOT-001", "2026-09-14T14:00:00Z", "2026-09-14T14:30:00Z", "occupied"),
    SeedSlot("SLOT-002", "2026-09-14T14:30:00Z", "2026-09-14T15:00:00Z", "available"),
    SeedSlot("SLOT-003", "2026-09-14T15:00:00Z", "2026-09-14T15:30:00Z", "available"),
    SeedSlot("SLOT-004", "2026-09-14T15:30:00Z", "2026-09-14T16:00:00Z", "occupied"),
    SeedSlot("SLOT-005", "2026-09-15T14:00:00Z", "2026-09-15T14:30:00Z", "available"),
    SeedSlot("SLOT-006", "2026-09-15T14:30:00Z", "2026-09-15T15:00:00Z", "occupied"),
    SeedSlot("SLOT-007", "2026-09-15T15:00:00Z", "2026-09-15T15:30:00Z", "available"),
    SeedSlot("SLOT-008", "2026-09-15T15:30:00Z", "2026-09-15T16:00:00Z", "available"),
)


def slot_to_dict(slot: AppointmentSlot) -> dict[str, str]:
    return {
        "id": slot.id,
        "dentist_name": slot.dentist_name,
        "starts_at": slot.starts_at,
        "ends_at": slot.ends_at,
        "status": slot.status,
    }


def load_schedule(session: Session) -> list[AppointmentSlot]:
    return list(
        session.scalars(
            select(AppointmentSlot).order_by(
                AppointmentSlot.starts_at,
                AppointmentSlot.id,
            )
        ).all()
    )


def schedule_payload(session: Session) -> dict:
    slots = load_schedule(session)
    return {
        "dentist_name": DENTIST_NAME,
        "demo_dates": list(DEMO_DATES),
        "slots": [slot_to_dict(slot) for slot in slots],
    }


def seed_if_empty(session: Session) -> int:
    """Insert the demo schedule when no slots exist. Returns inserted count."""
    existing = session.scalars(select(AppointmentSlot.id).limit(1)).first()
    if existing is not None:
        return 0
    _insert_seed_slots(session)
    session.commit()
    return len(SEED_SLOTS)


def reset_calendar(session: Session) -> None:
    """Remove demo bookings and restore the documented initial schedule."""
    session.execute(delete(RequestEvent))
    session.execute(delete(IdempotencyRecord))
    session.execute(delete(Appointment))
    session.execute(delete(AppointmentSlot))
    _insert_seed_slots(session)
    session.commit()


def _insert_seed_slots(session: Session) -> None:
    session.add_all(
        AppointmentSlot(
            id=slot.id,
            dentist_name=DENTIST_NAME,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
            status=slot.status,
        )
        for slot in SEED_SLOTS
    )
