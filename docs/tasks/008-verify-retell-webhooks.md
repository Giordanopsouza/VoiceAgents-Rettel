---
id: 008-verify-retell-webhooks
feature: retell
status: pending
---

# Verify Retell custom-function requests

## Scope
Add a reusable FastAPI boundary that captures the raw request body and verifies `X-Retell-Signature` before any Retell custom function can read or mutate calendar state.

## Acceptance criteria
- [ ] Signature verification uses the exact raw request bytes.
- [ ] Missing or invalid signatures receive an unauthorized response.
- [ ] Valid signed payloads are parsed only after verification succeeds.
- [ ] Signature values and the Retell API key never appear in logs or error bodies.
- [ ] Local test configuration can exercise the boundary without weakening production verification.

## Out of scope
- Availability and booking payload mapping.
- Retell agent creation.
- Browser authentication.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Established request authenticity as a shared prerequisite for both Retell tools.
