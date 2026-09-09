---
id: 002-create-calendar-schema
feature: calendar
status: done
---

# Create the calendar persistence schema

## Scope
Add SQLite persistence for appointment slots, appointments, idempotency records, and request events, including constraints that protect booking invariants under concurrent requests.

## Acceptance criteria
- [x] The application initializes a new SQLite database without manual SQL steps.
- [x] Appointment slots have stable identifiers, start times, and availability state.
- [x] Appointments reference slots and have stable public appointment IDs.
- [x] Idempotency keys are unique at the database level.
- [x] A slot cannot hold more than one active appointment.
- [x] Request events can record timestamps, attempt numbers, outcomes, and related appointment IDs.

## Out of scope
- Seed data.
- HTTP endpoints.
- Failure injection.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Separated durable state and concurrency constraints from the API behavior that will consume them.

### [SWE] 2026-09-09 09:43 — Started schema
Implementing SQLite tables and booking invariants via SQLAlchemy `create_all` on startup.

### [SWE] 2026-09-09 09:48 — Schema in place
Added SQLAlchemy models for `appointment_slot`, `appointment`, `idempotency_record`, and `request_event`. Startup creates the SQLite file with WAL mode, foreign keys, a unique idempotency key, and a partial unique index of one active appointment per slot.

### [Tester] 2026-09-09 09:48 — Schema tests pass
`uv run pytest` passed (14 tests), including startup table creation, duplicate idempotency keys, and two active appointments on the same slot.
