---
id: 011-document-retell-conversation-flow
feature: retell
status: done
---

# Define the Retell Conversation Flow assets

## Scope
Create version-controlled prompts, tool schemas, node transitions, and exact dashboard settings for a deterministic dental availability-and-booking Conversation Flow.

## Acceptance criteria
- [x] The flow covers greeting, detail collection, availability lookup, slot selection, explicit confirmation, booking, and completion.
- [x] Booking cannot occur before the caller confirms dentist, date, and time.
- [x] The agent uses fictional-demo language and does not request contact, payment, or medical information.
- [x] Tool URLs, methods, schemas, timeout, and retry count are documented exactly.
- [x] The booking timeout is shorter than the Failure Lab's first-response delay.
- [x] The repository includes a compact flow diagram and a dashboard recreation checklist.

## Out of scope
- Programmatic creation of Retell resources.
- Multi-agent transfer.
- Production clinic prompts.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Made the manually configured Retell resource reproducible and reviewable from the repository.

### [SWE] 2026-09-09 14:22 — Started Conversation Flow assets
Documenting prompts, node transitions, dashboard settings, and exact custom-function HTTP contracts so the Retell agent can be recreated without API provisioning.

### [SWE] 2026-09-09 14:35 — Conversation Flow assets in place
Added `retell/conversation-flow.md` and `retell/conversation-flow.json`. Tool schemas now record URL, timeout, retry, and wrapped-payload settings. Booking is a function node reachable only after explicit confirmation; its 2000 ms timeout with `max_retry` 1 stays below the 3000 ms Failure Lab delay.

### [Tester] 2026-09-09 14:35 — Conversation Flow tests pass
`uv run pytest` passed (89 tests), including greeting-through-completion coverage, confirmation-gated booking, fictional-demo language, exact tool HTTP settings, booking timeout shorter than Failure Lab delay, and the checked-in diagram plus recreation checklist.
