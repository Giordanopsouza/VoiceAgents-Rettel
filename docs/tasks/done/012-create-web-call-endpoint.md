---
id: 012-create-web-call-endpoint
feature: retell
status: done
---

# Create the server-side web-call endpoint

## Scope
Add a backend endpoint that uses the server-held Retell API key and configured agent ID to create a web call without exposing credentials to the browser.

## Acceptance criteria
- [x] The backend calls Retell's Create Web Call API with the configured agent.
- [x] The browser receives only the fields required to join the web call.
- [x] Retell credentials and privileged response fields are never returned or logged.
- [x] Missing configuration and Retell API failures produce clear bounded errors.
- [x] The created call includes demo metadata suitable for correlating sanitized events.

## Out of scope
- Rendering call controls.
- Phone calls or purchased phone numbers.
- Creating the Retell agent through the API.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Isolated privileged Retell API access behind the Python server.

### [SWE] 2026-09-09 14:31 — Started web-call endpoint
Implementing `POST /api/web-calls` with server-held Retell credentials, demo metadata, and browser-safe session fields. Dashboard UI and rate limits stay out of this task.

### [SWE] 2026-09-09 14:52 — Web-call endpoint in place
Added `app/web_calls.py` and `POST /api/web-calls`. The endpoint gates on `LIVE_DEMO_ENABLED`, calls Retell's `POST /v2/create-web-call` with the configured agent and demo metadata, and returns only `access_token` and `call_id`. Missing configuration and Retell failures map to bounded JSON errors without exposing secrets.

### [Tester] 2026-09-09 14:52 — Web-call endpoint tests pass
`uv run pytest` passed (103 tests), including browser-safe response fields, configured agent and demo metadata, live-demo pause, missing Retell configuration, Retell HTTP and network failures, unexpected Retell payloads, and privileged-field omission.
