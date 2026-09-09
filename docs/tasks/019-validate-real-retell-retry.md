---
id: 019-validate-real-retell-retry
feature: quality
status: pending
---

# Validate the real Retell retry path

## Scope
Run the configured Retell Conversation Flow against the Failure Lab and preserve a sanitized end-to-end trace proving that a genuine timeout and retry result in one appointment.

## Acceptance criteria
- [ ] A real Retell web call completes the agreed dental booking conversation.
- [ ] The first booking request commits and exceeds Retell's configured timeout.
- [ ] Retell sends a subsequent booking attempt.
- [ ] Both attempts resolve to one appointment ID and one database appointment.
- [ ] The agent communicates a single verified booking outcome.
- [ ] A sanitized trace is checked in or seeded for read-only dashboard playback.
- [ ] Any mismatch between documented and observed Retell behavior is recorded and resolved before completion.

## Out of scope
- Claiming that Retell caused the injected failure.
- Benchmarking latency or reliability.
- Testing production telephone networks.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Required external evidence that the configured Retell platform actually exercises the intended retry path.
