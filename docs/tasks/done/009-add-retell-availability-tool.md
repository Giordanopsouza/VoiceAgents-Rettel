---
id: 009-add-retell-availability-tool
feature: retell
status: done
---

# Add the Retell availability custom function

## Scope
Expose a signed Retell-compatible `check_availability` endpoint that maps the Retell custom-function request into the calendar availability service and returns concise agent-friendly JSON.

## Acceptance criteria
- [x] The endpoint accepts Retell's documented wrapped custom-function payload.
- [x] The request is rejected unless its signature is valid.
- [x] Required arguments match the checked-in Retell tool schema.
- [x] The response gives the agent stable slot IDs and speakable date/time labels.
- [x] Invalid arguments produce a bounded response the agent can handle gracefully.

## Out of scope
- Appointment creation.
- Broad natural-language parsing in the backend.
- Conversation Flow configuration in Retell.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Kept Retell transport mapping separate from the reusable availability service.

### [SWE] 2026-09-09 14:06 — Started availability custom function
Implementing a signed `POST /retell/check_availability` adapter that unwraps Retell's documented payload, calls the calendar availability service, and returns speakable slot JSON. Appointment creation and Conversation Flow configuration stay out of this task.

### [SWE] 2026-09-09 14:15 — Availability custom function in place
Added `retell/check_availability.json` and `app/retell_availability.py`. The endpoint inherits `X-Retell-Signature` verification, maps `args.date` onto `record_availability_attempt`, and returns stable slot IDs with speakable labels (`14:30` is "2:30 PM"). Invalid or unwrapped arguments return `ok: false` JSON the agent can speak instead of an HTTP failure.

### [Tester] 2026-09-09 14:15 — Availability tool tests pass
`uv run pytest` passed (70 tests), including wrapped payloads, signature rejection, schema-required `date`, speakable Monday/Tuesday slots, occupied-slot omission, bounded invalid/unsupported/unwrapped errors, secret omission, and no dashboard-path timeline writes.
