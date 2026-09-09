---
id: 004-add-availability-service
feature: calendar
status: done
---

# Add the availability service and API

## Scope
Implement calendar availability lookup and expose it through a small JSON API that can serve both the dashboard and the Retell adapter.

## Acceptance criteria
- [x] Availability can be queried for the documented demo date range.
- [x] Occupied slots never appear as available.
- [x] The response uses stable slot IDs and unambiguous ISO timestamps.
- [x] Invalid dates and unsupported requests return structured client errors.
- [x] The service contains no Retell-specific parsing.

## Out of scope
- Booking creation.
- Natural-language date parsing.
- Retell webhook authentication.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Defined availability as reusable calendar logic beneath the Retell integration boundary.

### [SWE] 2026-09-09 10:50 — Started availability service
Implementing date-scoped calendar lookup and `GET /api/availability` without Retell payload parsing.

### [SWE] 2026-09-09 10:55 — Availability lookup in place
Added `app/availability.py` to return open Dr. Elena Voss slots for 2026-09-14 and 2026-09-15. Occupied rows are omitted. Invalid and out-of-range dates return structured 400 errors. `GET /api/availability` is a thin JSON wrapper around that service.

### [Tester] 2026-09-09 10:55 — Availability tests pass
`uv run python -m pytest` passed (25 tests), including both demo dates, occupied-slot exclusion, ISO slot IDs/timestamps, structured invalid/unsupported date errors, and a direct service call that rejects a wrapped Retell-style payload.
