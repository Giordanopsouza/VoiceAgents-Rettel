---
id: 012-create-web-call-endpoint
feature: retell
status: pending
---

# Create the server-side web-call endpoint

## Scope
Add a backend endpoint that uses the server-held Retell API key and configured agent ID to create a web call without exposing credentials to the browser.

## Acceptance criteria
- [ ] The backend calls Retell's Create Web Call API with the configured agent.
- [ ] The browser receives only the fields required to join the web call.
- [ ] Retell credentials and privileged response fields are never returned or logged.
- [ ] Missing configuration and Retell API failures produce clear bounded errors.
- [ ] The created call includes demo metadata suitable for correlating sanitized events.

## Out of scope
- Rendering call controls.
- Phone calls or purchased phone numbers.
- Creating the Retell agent through the API.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Isolated privileged Retell API access behind the Python server.
