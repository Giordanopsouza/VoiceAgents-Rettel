---
id: 014-connect-calendar-and-failure-controls
feature: dashboard
status: pending
---

# Connect the calendar and Failure Lab controls

## Scope
Wire the dashboard to live availability, failure-mode status, and reset APIs so an operator can prepare and observe a deterministic demonstration.

## Acceptance criteria
- [ ] The schedule displays available and occupied slots from the backend.
- [ ] The Failure Lab switch reflects and changes server state.
- [ ] Reset requires an explicit UI action and visibly restores the seed schedule.
- [ ] Controls prevent conflicting actions while requests are pending.
- [ ] API failures are shown without exposing internal stack traces.

## Out of scope
- Voice-call controls.
- Request timeline rendering.
- Editing slots or appointments manually.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Connected the operator-facing setup controls independently from call and evidence views.
