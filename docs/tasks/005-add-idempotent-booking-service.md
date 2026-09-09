---
id: 005-add-idempotent-booking-service
feature: calendar
status: pending
---

# Add the idempotent booking service

## Scope
Implement appointment creation with a caller-supplied idempotency key and transactional handling that returns the original appointment for a duplicate request.

## Acceptance criteria
- [ ] A first valid request creates one appointment and returns its stable ID.
- [ ] Repeating the same idempotency key and payload returns the original appointment without a second row.
- [ ] Reusing an idempotency key with a different payload returns a conflict error.
- [ ] Competing requests for the same slot cannot create two active appointments.
- [ ] Booking an unavailable or unknown slot returns a structured error.
- [ ] Only fictional patient names are required; no phone, email, or medical data is stored.

## Out of scope
- Retell payload parsing.
- Rescheduling and cancellation.
- External calendar providers.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Captured the core reliability invariant independently of transport and UI concerns.
