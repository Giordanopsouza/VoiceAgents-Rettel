---
id: 016-add-retell-web-call-ui
feature: dashboard
status: pending
---

# Add the Retell web-call experience

## Scope
Integrate Retell's supported web-call client into the dashboard so a visitor can start, observe, and end a real conversation with the configured agent.

## Acceptance criteria
- [ ] Starting a call obtains session data from the server-side web-call endpoint.
- [ ] Microphone permission is requested only after an explicit visitor action.
- [ ] The interface exposes connecting, active, ended, denied, and failed states.
- [ ] Ending or failing a call releases client resources and permits a clean retry.
- [ ] The active Retell call correlates with the event timeline shown on the same page.

## Out of scope
- PSTN phone calls.
- Recording audio in the application.
- Custom speech recognition or synthesis.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Added the real Retell interaction only after the observable backend and dashboard are available.
