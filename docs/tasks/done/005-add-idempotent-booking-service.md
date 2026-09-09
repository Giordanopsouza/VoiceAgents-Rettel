---
id: 005-add-idempotent-booking-service
feature: calendar
status: done
---

# Add the idempotent booking service

## Scope
Implement appointment creation with a caller-supplied idempotency key and transactional handling that returns the original appointment for a duplicate request.

## Acceptance criteria
- [x] A first valid request creates one appointment and returns its stable ID.
- [x] Repeating the same idempotency key and payload returns the original appointment without a second row.
- [x] Reusing an idempotency key with a different payload returns a conflict error.
- [x] Competing requests for the same slot cannot create two active appointments.
- [x] Booking an unavailable or unknown slot returns a structured error.
- [x] Only fictional patient names are required; no phone, email, or medical data is stored.

## Out of scope
- Retell payload parsing.
- Rescheduling and cancellation.
- External calendar providers.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Captured the core reliability invariant independently of transport and UI concerns.

### [SWE] 2026-09-09 11:12 — Started idempotent booking
Implementing transactional appointment creation with a caller-supplied idempotency key, payload fingerprinting, and slot locking. Retell payload parsing stays out of this service.

### [SWE] 2026-09-09 11:25 — Booking service in place
Added `app/booking.py` to create `APT-00N` rows, occupy the slot in the same transaction, and replay the original appointment when the same key and fingerprint return. Same key with a different payload is a conflict. SQLite writers use `BEGIN IMMEDIATE` so overlapping requests cannot insert two active appointments on one slot.

### [Tester] 2026-09-09 11:25 — Booking tests pass
`uv run python -m pytest` passed (32 tests), including first-book identity, idempotent replay, payload conflict, concurrent slot contention, unknown/unavailable structured errors, fictional-name-only storage, and rejection of wrapped Retell-style arguments.
