---
id: 003-seed-and-reset-demo-calendar
feature: calendar
status: pending
---

# Seed and reset the demo calendar

## Scope
Provide a deterministic fictional dental schedule and an operator reset operation so every demonstration can begin from the same state.

## Acceptance criteria
- [ ] The seed contains one fictional dentist and a small mix of available and occupied slots.
- [ ] Seed dates are suitable for a stable demo and are described consistently in the agent configuration.
- [ ] The reset operation removes demo-created appointments, idempotency records, and request events.
- [ ] Reset restores exactly the documented initial schedule.
- [ ] Reset is unavailable or protected when public live calls are disabled according to configuration.

## Out of scope
- Multiple dentists.
- Recurring schedules or timezone selection.
- Real patient or clinic data.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Made the fictional schedule and repeatable reset behavior an explicit demo dependency.
