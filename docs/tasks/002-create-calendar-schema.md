---
id: 002-create-calendar-schema
feature: calendar
status: pending
---

# Create the calendar persistence schema

## Scope
Add SQLite persistence for appointment slots, appointments, idempotency records, and request events, including constraints that protect booking invariants under concurrent requests.

## Acceptance criteria
- [ ] The application initializes a new SQLite database without manual SQL steps.
- [ ] Appointment slots have stable identifiers, start times, and availability state.
- [ ] Appointments reference slots and have stable public appointment IDs.
- [ ] Idempotency keys are unique at the database level.
- [ ] A slot cannot hold more than one active appointment.
- [ ] Request events can record timestamps, attempt numbers, outcomes, and related appointment IDs.

## Out of scope
- Seed data.
- HTTP endpoints.
- Failure injection.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Separated durable state and concurrency constraints from the API behavior that will consume them.
