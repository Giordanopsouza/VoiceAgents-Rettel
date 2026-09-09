---
id: 006-record-request-events
feature: failure-lab
status: pending
---

# Record an inspectable request event timeline

## Scope
Persist structured events for availability and booking attempts and expose a read API that lets the dashboard explain what occurred without exposing sensitive payloads.

## Acceptance criteria
- [ ] Every booking attempt records receipt, idempotency decision, appointment result, and response outcome.
- [ ] Events correlate by Retell call ID and idempotency key.
- [ ] Event responses omit API keys, signatures, access tokens, raw transcripts, and personal contact details.
- [ ] Events are returned in deterministic chronological order.
- [ ] The read API supports fetching the current demo session without accessing the database directly.

## Out of scope
- Browser rendering.
- General-purpose observability or log aggregation.
- Long-term production retention.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Turned backend behavior into sanitized evidence suitable for the engineering dashboard.
