---
id: 014-connect-calendar-and-failure-controls
feature: dashboard
status: done
---

# Connect the calendar and Failure Lab controls

## Scope
Wire the dashboard to live availability, failure-mode status, and reset APIs so an operator can prepare and observe a deterministic demonstration.

## Acceptance criteria
- [x] The schedule displays available and occupied slots from the backend.
- [x] The Failure Lab switch reflects and changes server state.
- [x] Reset requires an explicit UI action and visibly restores the seed schedule.
- [x] Controls prevent conflicting actions while requests are pending.
- [x] API failures are shown without exposing internal stack traces.

## Out of scope
- Voice-call controls.
- Request timeline rendering.
- Editing slots or appointments manually.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Connected the operator-facing setup controls independently from call and evidence views.

### [SWE] 2026-09-10 10:17 — Started calendar and Failure Lab controls
Wiring the dashboard to the schedule, Failure Lab, and reset APIs so an operator can prepare a deterministic demo without touching the timeline or voice call.

### [SWE] 2026-09-10 10:30 — Calendar and Failure Lab controls wired
Added `GET /api/schedule` for the full seeded calendar, including occupied rows. The dashboard loads that schedule and Failure Lab status, lets the operator toggle lost-response mode, and restores the seed only from the reset button. Controls lock while a request is in flight, and API errors stay bounded.

### [Tester] 2026-09-10 10:30 — Tests pass
`uv run pytest` passed (117 tests), including schedule reads with occupied slots, booking-then-reset restoration, live-demo-paused readability, and dashboard hooks for the live controls.
