---
id: 008-verify-retell-webhooks
feature: retell
status: done
---

# Verify Retell custom-function requests

## Scope
Add a reusable FastAPI boundary that captures the raw request body and verifies `X-Retell-Signature` before any Retell custom function can read or mutate calendar state.

## Acceptance criteria
- [x] Signature verification uses the exact raw request bytes.
- [x] Missing or invalid signatures receive an unauthorized response.
- [x] Valid signed payloads are parsed only after verification succeeds.
- [x] Signature values and the Retell API key never appear in logs or error bodies.
- [x] Local test configuration can exercise the boundary without weakening production verification.

## Out of scope
- Availability and booking payload mapping.
- Retell agent creation.
- Browser authentication.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Established request authenticity as a shared prerequisite for both Retell tools.

### [SWE] 2026-09-09 12:16 — Started signature boundary
Implementing raw-body HMAC verification for `X-Retell-Signature` as a shared FastAPI dependency, without a production skip switch.

### [SWE] 2026-09-09 12:25 — Signature boundary in place
Added `app/retell_auth.py` with Retell's HMAC-SHA256 scheme over the exact raw body, a 5-minute replay window, and `retell_router` so later custom functions inherit verification. JSON is parsed only after the signature succeeds. Tests sign with a dedicated key and `now_ms` instead of disabling checks.

### [Tester] 2026-09-09 12:25 — Signature tests pass
`uv run pytest` passed (59 tests), including missing/invalid/tampered signatures, parse-after-verify ordering, secret omission from error bodies, empty API key rejection, and no calendar mutation on unauthorized requests.
