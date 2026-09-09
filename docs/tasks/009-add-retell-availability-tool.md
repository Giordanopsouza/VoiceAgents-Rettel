---
id: 009-add-retell-availability-tool
feature: retell
status: pending
---

# Add the Retell availability custom function

## Scope
Expose a signed Retell-compatible `check_availability` endpoint that maps the Retell custom-function request into the calendar availability service and returns concise agent-friendly JSON.

## Acceptance criteria
- [ ] The endpoint accepts Retell's documented wrapped custom-function payload.
- [ ] The request is rejected unless its signature is valid.
- [ ] Required arguments match the checked-in Retell tool schema.
- [ ] The response gives the agent stable slot IDs and speakable date/time labels.
- [ ] Invalid arguments produce a bounded response the agent can handle gracefully.

## Out of scope
- Appointment creation.
- Broad natural-language parsing in the backend.
- Conversation Flow configuration in Retell.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Kept Retell transport mapping separate from the reusable availability service.
