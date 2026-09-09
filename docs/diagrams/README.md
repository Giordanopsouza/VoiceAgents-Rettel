# Application diagrams

These Mermaid source files describe the Retell dental-booking prototype from complementary viewpoints:

1. [`01-system-architecture.mmd`](01-system-architecture.mmd) — components and trust boundaries.
2. [`02-retell-conversation-flow.mmd`](02-retell-conversation-flow.mmd) — what the voice agent does during a call.
3. [`03-normal-booking-sequence.mmd`](03-normal-booking-sequence.mmd) — the successful one-request path.
4. [`04-lost-response-retry-sequence.mmd`](04-lost-response-retry-sequence.mmd) — the central two-attempt, one-appointment demonstration.
5. [`05-booking-state-model.mmd`](05-booking-state-model.mmd) — backend states and invariant-preserving decisions.
6. [`06-railway-deployment.mmd`](06-railway-deployment.mmd) — public deployment and secret boundaries.

The SQLite schema, column list, and uniqueness invariants live in [`docs/database.md`](../database.md).

Render any source file with a Mermaid-compatible editor or CLI. The `.mmd` files remain the canonical versions.
