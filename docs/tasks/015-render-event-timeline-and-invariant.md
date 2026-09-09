---
id: 015-render-event-timeline-and-invariant
feature: dashboard
status: pending
---

# Render the request timeline and reliability invariant

## Scope
Display sanitized request events as they occur and calculate the central proof that multiple attempts resolved to one appointment.

## Acceptance criteria
- [ ] The timeline updates during a demo without a manual page reload.
- [ ] Each attempt shows its number, relative timing, outcome, shortened idempotency key, and appointment ID.
- [ ] The final result displays `2 API attempts · 1 appointment · duplicate prevented` only when supported by backend data.
- [ ] Normal one-attempt bookings receive an accurate, different result state.
- [ ] Incomplete and failed runs never display a success claim.

## Out of scope
- Raw Retell transcripts.
- General analytics charts.
- Editing or deleting individual events.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Made the project's central claim computable from evidence rather than hard-coded copy.
