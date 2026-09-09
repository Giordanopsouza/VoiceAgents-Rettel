---
id: 017-add-public-demo-guardrails
feature: deployment
status: pending
---

# Add public-demo guardrails

## Scope
Protect Retell usage and demo state with a server-side live-call switch, request limits, bounded input, and clear paused behavior while leaving the recorded evidence public.

## Acceptance criteria
- [ ] `LIVE_DEMO_ENABLED=false` prevents new web-call creation server-side.
- [ ] The dashboard accurately shows whether live calls are enabled.
- [ ] Per-client and global call limits are enforced on the server.
- [ ] Tool payload sizes and relevant string fields have conservative limits.
- [ ] Guardrail responses are understandable and do not disclose internal configuration.
- [ ] Public read-only access to the saved demonstration remains available while calls are paused.

## Out of scope
- User accounts.
- Billing administration.
- Protection suitable for an unrestricted production service.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Separated public demo safety from the core call implementation.
