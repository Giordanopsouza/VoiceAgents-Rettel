---
id: 018-add-automated-reliability-tests
feature: quality
status: pending
---

# Add automated reliability tests

## Scope
Create focused Python tests for calendar invariants, signature enforcement, idempotent replays, concurrent requests, and the lost-response retry sequence.

## Acceptance criteria
- [ ] Two identical booking requests produce one appointment row and the same appointment ID.
- [ ] Reusing a key with different booking details is rejected.
- [ ] Concurrent attempts cannot double-book a slot.
- [ ] The lost-response test records a delayed first attempt and a successful idempotent replay.
- [ ] Invalid Retell signatures cannot access or mutate calendar state.
- [ ] The documented test command passes from a clean local setup.

## Out of scope
- Testing Retell's own infrastructure.
- Browser visual regression tests.
- Load or penetration testing.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Defined tests around material boundaries and invariants rather than mirroring implementation details.
