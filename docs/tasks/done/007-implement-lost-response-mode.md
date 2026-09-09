---
id: 007-implement-lost-response-mode
feature: failure-lab
status: done
---

# Implement the lost-response failure mode

## Scope
Add a deterministic Failure Lab mode that commits the first booking and then delays its response beyond the configured Retell timeout while allowing the retry to return the existing appointment.

## Acceptance criteria
- [x] Failure mode can be enabled and disabled through an operator API.
- [x] Normal mode responds without an artificial delay.
- [x] In failure mode, the first matching booking commits before its response is delayed.
- [x] Only the first attempt for that idempotency key receives the artificial delay.
- [x] A concurrent retry returns the existing appointment ID and does not block on the first response.
- [x] The event timeline distinguishes `created_then_response_delayed` from `duplicate_returned`.

## Out of scope
- Random failure injection.
- HTTP 500 and permanent-failure scenarios.
- Caller interruption behavior.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Specified a real ambiguous-outcome timeout rather than a visual or mocked approximation.

### [SWE] 2026-09-09 12:05 — Started lost-response mode
Implementing an operator-controlled Failure Lab that commits the first booking, records `created_then_response_delayed`, then sleeps past the configured timeout so a concurrent retry can return the existing appointment.

### [SWE] 2026-09-09 12:12 — Lost-response mode in place
Added `app/failure_lab.py` with `GET`/`PUT /api/failure-lab` for the operator switch. The first successful create for a key commits the appointment, records `created_then_response_delayed`, then waits `FAILURE_LAB_DELAY_SECONDS`. A retry of the same key returns the existing appointment immediately as `duplicate_returned`. Demo reset clears delayed-key tracking so the next run can inject the timeout again.

### [Tester] 2026-09-09 12:12 — Lost-response tests pass
`uv run python -m pytest` passed (49 tests), including operator enable/disable, no delay in normal mode, commit-before-delay, first-attempt-only delay, concurrent retry of the same appointment ID, timeline outcomes, and delay-must-exceed-timeout settings validation.
