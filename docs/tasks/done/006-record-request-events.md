---
id: 006-record-request-events
feature: failure-lab
status: done
---

# Record an inspectable request event timeline

## Scope
Persist structured events for availability and booking attempts and expose a read API that lets the dashboard explain what occurred without exposing sensitive payloads.

## Acceptance criteria
- [x] Every booking attempt records receipt, idempotency decision, appointment result, and response outcome.
- [x] Events correlate by Retell call ID and idempotency key.
- [x] Event responses omit API keys, signatures, access tokens, raw transcripts, and personal contact details.
- [x] Events are returned in deterministic chronological order.
- [x] The read API supports fetching the current demo session without accessing the database directly.

## Out of scope
- Browser rendering.
- General-purpose observability or log aggregation.
- Long-term production retention.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Turned backend behavior into sanitized evidence suitable for the engineering dashboard.

### [SWE] 2026-09-09 11:38 — Started request event timeline
Implementing sanitized persistence for availability and booking attempts, plus a read API for the current demo session. Browser rendering stays out of this task.

### [SWE] 2026-09-09 11:50 — Event timeline in place
Added `app/events.py` to record availability and booking attempts against the existing `request_event` table. Booking wrappers emit receipt, idempotency decision, appointment result, and response outcome, correlated by sanitized `call_id` and idempotency key. `GET /api/events` returns the current demo session in chronological order and stays readable while the live demo is paused.

### [Tester] 2026-09-09 11:50 — Event timeline tests pass
`uv run python -m pytest` passed (42 tests), including four-event booking attempts, retry correlation, secret/PII omission, chronological order, `GET /api/events` as the demo-session read API, availability attempt recording, and failed-booking evidence.
