---
id: 003-seed-and-reset-demo-calendar
feature: calendar
status: done
---

# Seed and reset the demo calendar

## Scope
Provide a deterministic fictional dental schedule and an operator reset operation so every demonstration can begin from the same state.

## Acceptance criteria
- [x] The seed contains one fictional dentist and a small mix of available and occupied slots.
- [x] Seed dates are suitable for a stable demo and are described consistently in the agent configuration.
- [x] The reset operation removes demo-created appointments, idempotency records, and request events.
- [x] Reset restores exactly the documented initial schedule.
- [x] Reset is unavailable or protected when public live calls are disabled according to configuration.

## Out of scope
- Multiple dentists.
- Recurring schedules or timezone selection.
- Real patient or clinic data.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Made the fictional schedule and repeatable reset behavior an explicit demo dependency.

### [SWE] 2026-09-09 10:32 — Started seed and reset
Implementing a fixed two-day Dr. Elena Voss schedule, startup seeding of empty databases, and a live-demo-gated reset endpoint.

### [SWE] 2026-09-09 10:36 — Seed and reset in place
Added `app/seed.py` with eight 30-minute slots for Dr. Elena Voss on 14–15 September 2026. Startup seeds an empty database. `POST /api/demo/reset` restores that schedule after deleting appointments, idempotency records, and request events, and returns 403 when `LIVE_DEMO_ENABLED=false`.

### [Tester] 2026-09-09 10:36 — Seed tests pass
`uv run pytest` passed (19 tests), including startup seeding, occupied seed rows without appointments, reset restoration, and the live-demo-gated 403.
