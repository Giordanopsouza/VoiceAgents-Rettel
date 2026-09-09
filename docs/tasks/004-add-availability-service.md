---
id: 004-add-availability-service
feature: calendar
status: pending
---

# Add the availability service and API

## Scope
Implement calendar availability lookup and expose it through a small JSON API that can serve both the dashboard and the Retell adapter.

## Acceptance criteria
- [ ] Availability can be queried for the documented demo date range.
- [ ] Occupied slots never appear as available.
- [ ] The response uses stable slot IDs and unambiguous ISO timestamps.
- [ ] Invalid dates and unsupported requests return structured client errors.
- [ ] The service contains no Retell-specific parsing.

## Out of scope
- Booking creation.
- Natural-language date parsing.
- Retell webhook authentication.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Defined availability as reusable calendar logic beneath the Retell integration boundary.
