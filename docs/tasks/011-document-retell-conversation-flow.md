---
id: 011-document-retell-conversation-flow
feature: retell
status: pending
---

# Define the Retell Conversation Flow assets

## Scope
Create version-controlled prompts, tool schemas, node transitions, and exact dashboard settings for a deterministic dental availability-and-booking Conversation Flow.

## Acceptance criteria
- [ ] The flow covers greeting, detail collection, availability lookup, slot selection, explicit confirmation, booking, and completion.
- [ ] Booking cannot occur before the caller confirms dentist, date, and time.
- [ ] The agent uses fictional-demo language and does not request contact, payment, or medical information.
- [ ] Tool URLs, methods, schemas, timeout, and retry count are documented exactly.
- [ ] The booking timeout is shorter than the Failure Lab's first-response delay.
- [ ] The repository includes a compact flow diagram and a dashboard recreation checklist.

## Out of scope
- Programmatic creation of Retell resources.
- Multi-agent transfer.
- Production clinic prompts.

## Log
### [PA] 2026-09-09 09:06 — Grooming
Made the manually configured Retell resource reproducible and reviewable from the repository.
