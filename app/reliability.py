from datetime import datetime

DUPLICATE_PREVENTED = "2 API attempts · 1 appointment · duplicate prevented"
SINGLE_BOOKED = "1 API attempt · 1 appointment · booked"
_CREATE_OUTCOMES = frozenset({"created_returned", "created_then_response_delayed"})
_REPLAY_OUTCOMES = frozenset({"duplicate_returned"})


def dashboard_evidence(events: list[dict]) -> dict:
    """Shape sanitized events into timeline attempts and a reliability result."""
    attempts = build_attempts(events)
    return {
        "events": events,
        "attempts": attempts,
        "reliability": summarize_reliability(attempts),
    }


def build_attempts(events: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    for event in events:
        key = _attempt_key(event)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(event)

    origin = _parse_timestamp(events[0]["created_at"]) if events else None
    attempts = []
    for key in order:
        kind, _correlation, number = key
        group = groups[key]
        receipt = next(
            (event for event in group if event["event_type"] == "receipt"),
            group[0],
        )
        response = next(
            (event for event in group if event["event_type"] == "response_outcome"),
            None,
        )
        appointment_id = next(
            (event["appointment_id"] for event in group if event.get("appointment_id")),
            None,
        )
        started = _parse_timestamp(receipt["created_at"])
        relative_s = 0
        if origin is not None and started is not None:
            relative_s = int((started - origin).total_seconds())
        idempotency_key = receipt.get("idempotency_key")
        attempts.append(
            {
                "attempt_number": number,
                "kind": kind,
                "relative_s": relative_s,
                "outcome": None if response is None else response["outcome"],
                "complete": response is not None,
                "idempotency_key": idempotency_key,
                "idempotency_key_short": shorten_idempotency_key(idempotency_key),
                "appointment_id": appointment_id,
            }
        )
    return attempts


def summarize_reliability(attempts: list[dict]) -> dict[str, str | None]:
    booking = [attempt for attempt in attempts if attempt["kind"] == "booking"]
    if not booking:
        return {"state": "empty", "headline": None}

    incomplete = any(not attempt["complete"] for attempt in booking)
    appointment_ids = {
        attempt["appointment_id"]
        for attempt in booking
        if attempt.get("appointment_id")
    }
    created = [
        attempt for attempt in booking if attempt.get("outcome") in _CREATE_OUTCOMES
    ]
    replayed = [
        attempt for attempt in booking if attempt.get("outcome") in _REPLAY_OUTCOMES
    ]
    keys = {attempt.get("idempotency_key") for attempt in booking}

    if (
        len(booking) == 2
        and not incomplete
        and len(appointment_ids) == 1
        and len(keys) == 1
        and created
        and replayed
    ):
        return {"state": "duplicate_prevented", "headline": DUPLICATE_PREVENTED}

    if (
        len(booking) == 1
        and booking[0].get("outcome") == "created_returned"
        and len(appointment_ids) == 1
    ):
        return {"state": "booked", "headline": SINGLE_BOOKED}

    if incomplete or (
        len(booking) == 1
        and booking[0].get("outcome") == "created_then_response_delayed"
    ):
        return {"state": "incomplete", "headline": None}

    return {"state": "failed", "headline": None}


def shorten_idempotency_key(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= 16:
        return key
    return f"{key[:8]}…{key[-6:]}"


def _attempt_key(event: dict) -> tuple:
    number = event.get("attempt_number")
    if event.get("idempotency_key"):
        return ("booking", event["idempotency_key"], number)
    return ("availability", event.get("call_id"), number)


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
