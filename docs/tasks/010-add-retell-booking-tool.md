---
id: 010-add-retell-booking-tool
feature: retell
status: pending
---

# Add the Retell booking custom function

## Scope
Expose a signed Retell-compatible `book_appointment` endpoint that derives a stable idempotency key from the call and canonical booking details, then invokes the booking and Failure Lab services.

## Acceptance criteria
- [ ] The endpoint requires a valid Retell signature.
- [ ] The idempotency key includes the Retell `call_id`, slot identity, dentist identity, and normalized fictional patient name.
- [ ] The raw key inputs are canonicalized deterministically and the stored key is safe to display.
- [ ] Retell retries receive the same appointment ID as the original attempt.
- [ ] The response clearly distinguishes a newly created appointment from an idempotent replay without prompting duplicate verbal confirmations.
- [ ] The checked-in tool schema requires explicit booking confirmation data.

## Out of scope
- Cancellation or rescheduling tools.
- Parsing a tool-call ID from the transcript.
- Sending confirmations by email or SMS.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Connected the core invariant to Retell's real call identity and retry path.
