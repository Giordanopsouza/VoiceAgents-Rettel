---
id: 007-implement-lost-response-mode
feature: failure-lab
status: pending
---

# Implement the lost-response failure mode

## Scope
Add a deterministic Failure Lab mode that commits the first booking and then delays its response beyond the configured Retell timeout while allowing the retry to return the existing appointment.

## Acceptance criteria
- [ ] Failure mode can be enabled and disabled through an operator API.
- [ ] Normal mode responds without an artificial delay.
- [ ] In failure mode, the first matching booking commits before its response is delayed.
- [ ] Only the first attempt for that idempotency key receives the artificial delay.
- [ ] A concurrent retry returns the existing appointment ID and does not block on the first response.
- [ ] The event timeline distinguishes `created_then_response_delayed` from `duplicate_returned`.

## Out of scope
- Random failure injection.
- HTTP 500 and permanent-failure scenarios.
- Caller interruption behavior.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Specified a real ambiguous-outcome timeout rather than a visual or mocked approximation.
