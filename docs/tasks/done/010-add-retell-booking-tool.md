---
id: 010-add-retell-booking-tool
feature: retell
status: done
---

# Add the Retell booking custom function

## Scope
Expose a signed Retell-compatible `book_appointment` endpoint that derives a stable idempotency key from the call and canonical booking details, then invokes the booking and Failure Lab services.

## Acceptance criteria
- [x] The endpoint requires a valid Retell signature.
- [x] The idempotency key includes the Retell `call_id`, slot identity, dentist identity, and normalized fictional patient name.
- [x] The raw key inputs are canonicalized deterministically and the stored key is safe to display.
- [x] Retell retries receive the same appointment ID as the original attempt.
- [x] The response clearly distinguishes a newly created appointment from an idempotent replay without prompting duplicate verbal confirmations.
- [x] The checked-in tool schema requires explicit booking confirmation data.

## Out of scope
- Cancellation or rescheduling tools.
- Parsing a tool-call ID from the transcript.
- Sending confirmations by email or SMS.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Connected the core invariant to Retell's real call identity and retry path.

### [SWE] 2026-09-09 14:10 — Started booking custom function
Implementing a signed `POST /retell/book_appointment` adapter that derives a display-safe idempotency key from call, slot, dentist, and normalized patient name, then invokes booking and Failure Lab. Cancellation, rescheduling, and transcript tool-call IDs stay out of this task.

### [SWE] 2026-09-09 14:20 — Booking custom function in place
Added `retell/book_appointment.json` and `app/retell_booking.py`. The endpoint inherits `X-Retell-Signature` verification, requires `confirmed=true` plus dentist/slot/patient args, hashes a display-safe `bk_` key, and returns `replayed` plus a speak-once message. Failure Lab delays the first create; a retry returns `APT-001` without another insert.

### [Tester] 2026-09-09 14:20 — Booking tool tests pass
`uv run pytest` passed (83 tests), including signature rejection, schema-required confirmation, canonical key identity, retry of the same appointment ID, replay vs create messages, bounded unwrapped/unconfirmed/dentist/slot errors, secret omission, and Failure Lab delay-then-replay through the HTTP endpoint.
