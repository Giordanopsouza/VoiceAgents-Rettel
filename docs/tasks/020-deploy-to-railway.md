---
id: 020-deploy-to-railway
feature: deployment
status: pending
---

# Deploy the demo to Railway

## Scope
Deploy the single FastAPI service to Railway with a public HTTPS URL, persistent SQLite storage, health checking, and server-side secrets.

## Acceptance criteria
- [ ] Railway builds and starts the application reproducibly from repository configuration.
- [ ] A persistent volume holds the SQLite database at the configured path.
- [ ] Retell API key, agent ID, and operator settings are configured as Railway variables and absent from the repository.
- [ ] The public health endpoint succeeds after deployment and restart.
- [ ] Retell custom-function URLs point to the deployed HTTPS endpoints.
- [ ] Restarting or redeploying does not remove the saved demonstration trace.

## Out of scope
- Multiple replicas or high availability.
- A custom domain.
- Production service-level objectives.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Selected the agreed single-service Railway deployment with persistent storage.
