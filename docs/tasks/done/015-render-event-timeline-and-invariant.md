---
id: 015-render-event-timeline-and-invariant
feature: dashboard
status: done
---

# Render the request timeline and reliability invariant

## Scope
Display sanitized request events as they occur and calculate the central proof that multiple attempts resolved to one appointment.

## Acceptance criteria
- [x] The timeline updates during a demo without a manual page reload.
- [x] Each attempt shows its number, relative timing, outcome, shortened idempotency key, and appointment ID.
- [x] The final result displays `2 API attempts · 1 appointment · duplicate prevented` only when supported by backend data.
- [x] Normal one-attempt bookings receive an accurate, different result state.
- [x] Incomplete and failed runs never display a success claim.

## Out of scope
- Raw Retell transcripts.
- General analytics charts.
- Editing or deleting individual events.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Made the project's central claim computable from evidence rather than hard-coded copy.

### [SWE] 2026-09-10 10:32 — Started timeline and invariant
Computing attempt summaries and the reliability result from sanitized request events, then polling them into the dashboard.

### [SWE] 2026-09-10 10:48 — Timeline and invariant wired
Added `app/reliability.py` to group sanitized events into attempts and compute the result from evidence. `GET /api/events` now returns attempts plus a reliability summary. The dashboard polls that payload, renders each attempt, and only shows the duplicate-prevented headline when two attempts share one appointment.

### [Tester] 2026-09-10 10:48 — Tests pass
`uv run pytest` passed (128 tests), including duplicate-prevented vs single-booking vs delayed-incomplete vs rejected vs two-appointment cases, and dashboard hooks for the live timeline.
