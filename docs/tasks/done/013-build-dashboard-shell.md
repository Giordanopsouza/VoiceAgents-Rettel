---
id: 013-build-dashboard-shell
feature: dashboard
status: done
---

# Build the engineering dashboard shell

## Scope
Create a responsive static interface served by FastAPI with clear regions for the voice call, dental schedule, Failure Lab, event timeline, and reliability result.

## Acceptance criteria
- [x] The page establishes the fictional dental customer scenario immediately.
- [x] The integration path and current demo state are understandable without reading the README.
- [x] Empty, loading, ready, and error states have defined treatments.
- [x] The layout works at common desktop and mobile widths.
- [x] Keyboard focus, labels, contrast, and reduced-motion behavior support basic accessibility.

## Out of scope
- Live API data.
- Retell voice SDK integration.
- A separate marketing site.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Scoped one evidence-centered interface rather than parallel clinic and engineering sites.

### [SWE] 2026-09-09 17:58 — Dashboard shell
Added responsive static dashboard at `/` with panel regions, state treatments, embedded demo config, and accessibility affordances.

### [Tester] 2026-09-09 17:59 — Tests pass
`uv run pytest` passed (111 tests). `GET /` returns the dashboard shell and static assets serve correctly.
