# Retell Conversation Flow

Manual Retell dashboard configuration for the fictional Dr. Elena Voss booking demonstration. Do not create these resources through the Retell API. Copy the values below; keep [check_availability.json](check_availability.json) and [book_appointment.json](book_appointment.json) as the parameter schemas.

The compact graph is [docs/diagrams/02-retell-conversation-flow.mmd](../docs/diagrams/02-retell-conversation-flow.mmd). Machine-checkable node IDs, edges, and dashboard fields are in [conversation-flow.json](conversation-flow.json).

## Why these settings

`book_appointment` times out at **2000 ms** and retries **once**. Failure Lab delays the first successful create by **3000 ms**. Retell therefore retries after the lost first response, and the calendar returns the original appointment. Availability uses a longer 10000 ms timeout and does not retry, so a slow lookup does not create extra timeline rows.

The booking function node is reachable from only one edge: the caller explicitly confirmed dentist, date, and time.

## Clinic facts the agent must speak

One dentist, **Dr. Elena Voss**. Times are stored as UTC and spoken with the same clock values (`14:30` is "2:30 PM").

| Slot ID | Date | Spoken time | Seed status |
| --- | --- | --- | --- |
| SLOT-001 | Monday 14 September 2026 | 2:00 PM | occupied |
| SLOT-002 | Monday 14 September 2026 | 2:30 PM | available |
| SLOT-003 | Monday 14 September 2026 | 3:00 PM | available |
| SLOT-004 | Monday 14 September 2026 | 3:30 PM | occupied |
| SLOT-005 | Tuesday 15 September 2026 | 2:00 PM | available |
| SLOT-006 | Tuesday 15 September 2026 | 2:30 PM | occupied |
| SLOT-007 | Tuesday 15 September 2026 | 3:00 PM | available |
| SLOT-008 | Tuesday 15 September 2026 | 3:30 PM | available |

## Dashboard recreation checklist

Replace `<PUBLIC_HOST>` with the public HTTPS hostname of this service (the Railway domain after task 020). Localhost is not reachable from Retell.

### Agent

- [ ] Create a **Conversation Flow** agent named `Dental Booking Reliability Lab`.
- [ ] Response engine: Conversation Flow. Flex Mode: off.
- [ ] Who speaks first: **Agent**. Start node: `Greet`.
- [ ] Language: English (`en-US`).
- [ ] Model: GPT-4.1, cascading. Temperature: `0.3`.
- [ ] Voice: any English voice. Do not override voice or model on individual nodes.
- [ ] Knowledge base: none. Post-call extraction: none.
- [ ] End call on silence: 30 seconds. Max call duration: 5 minutes.
- [ ] Boosted keywords: `Elena`, `Voss`, `Jordan Hale`, `Monday`, `Tuesday`.
- [ ] Paste the global prompt from [conversation-flow.json](conversation-flow.json) (`global_prompt`) into Global Settings.
- [ ] After the flow exists, copy the agent ID into `RETELL_AGENT_ID`. Keep `RETELL_API_KEY` on the server only.

### Custom functions

Create both functions before wiring function nodes. Paste each repository JSON schema into the parameter editor (**JSON**, not the form builder).

Shared HTTP settings:

| Field | `check_availability` | `book_appointment` |
| --- | --- | --- |
| Method | `POST` | `POST` |
| URL | `https://<PUBLIC_HOST>/retell/check_availability` | `https://<PUBLIC_HOST>/retell/book_appointment` |
| Timeout (ms) | `10000` | `2000` |
| `max_retry` | `0` | `1` |
| Payload: args only / `args_at_root` | Off / `false` | Off / `false` |
| Query parameters | none | none |
| Extra headers | none | none |

Retell adds `X-Retell-Signature` and the wrapped body (`name`, `call`, `args`) when args-only is off. The Python adapters require that wrapper, including `call.call_id` on booking.

- [ ] `check_availability`: name, description, and parameters from [check_availability.json](check_availability.json). Timeout `10000`. `max_retry` `0`.
- [ ] `book_appointment`: name, description, and parameters from [book_appointment.json](book_appointment.json). Timeout `2000`. `max_retry` `1`.
- [ ] Confirm the booking timeout is **shorter** than `FAILURE_LAB_DELAY_SECONDS` (default 3 seconds / 3000 ms).
- [ ] Confirm `confirmed` is required on `book_appointment` and the description says not to call it when `confirmed` is false.

### Nodes and transitions

Name nodes exactly as below so call history is readable. Function nodes execute on entry; they are not subagent nodes, so the LLM cannot book during small talk.

| Node | Type | Instruction | Transitions |
| --- | --- | --- | --- |
| Greet | Conversation | Static sentence. Skip Response on. | Skip Response → Collect details |
| Collect details | Conversation | Prompt. | Prompt: caller gave a fictional name and date → Look up availability |
| Look up availability | Function (`check_availability`) | Wait for result on. Speak during execution, static: `Let me check Dr. Elena Voss's fictional schedule.` Speak after execution off. | Prompt: `ok` true and at least one slot → Offer and select a slot. Else → No matching availability |
| No matching availability | Conversation | Prompt. | Prompt: caller will try another date → Collect details |
| Offer and select a slot | Conversation | Prompt. | Prompt: caller picked one offered slot → Confirm dentist, date, and time |
| Confirm dentist, date, and time | Conversation | Prompt. **No tools.** | Prompt: caller explicitly confirmed dentist, date, and time → Book appointment. Prompt: caller wants a change → Revise the request |
| Revise the request | Conversation | Prompt. | Always → Collect details |
| Book appointment | Function (`book_appointment`) | Wait for result on. Speak during execution, static: `One moment, I am booking that fictional appointment.` Speak after execution off. | Prompt: `ok` true (created or replayed) → Confirm the verified appointment. Prompt: `slot_unavailable` → Slot no longer open. Else → Booking could not be verified |
| Confirm the verified appointment | Conversation | Prompt. Skip Response on. | Skip Response → End after booking |
| Slot no longer open | Conversation | Prompt. | Prompt: caller wants other times → Look up availability |
| Booking could not be verified | Conversation | Prompt. Skip Response on. | Skip Response → End after unverified booking |
| End after booking | End | Speak during execution, static goodbye. | — |
| End after unverified booking | End | Speak during execution, static goodbye. | — |

Copy each node's `instruction.text` from [conversation-flow.json](conversation-flow.json). Do not attach `book_appointment` to any node except **Book appointment**. Do not add an else edge from Confirm to Book appointment.

### Smoke check in the Retell canvas

- [ ] The agent greets with fictional-demo language.
- [ ] Collect details asks for a fictional name and Monday 14 or Tuesday 15 September 2026.
- [ ] Availability lookup runs only after a date is collected.
- [ ] Offered times match returned `time_label` values; occupied seed slots are absent.
- [ ] Booking does not run until the caller confirms dentist, date, and time.
- [ ] A successful or replayed result is spoken once; the agent does not ask for another confirmation.
