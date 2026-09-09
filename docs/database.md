# Database

SQLite file at `DATABASE_PATH` (`data/calendar.sqlite` locally; a persistent volume path on Railway). There is no tenant model and no Postgres/RLS: one process owns the file. The application creates missing tables on startup (`SQLAlchemy metadata.create_all`); there is no Alembic migration runner.

Target after task 002: `appointment_slot`, `appointment`, `idempotency_record`, and `request_event`. Seed data (task 003) is the documented two-day Dr. Elena Voss schedule below; startup inserts it only when `appointment_slot` is empty. WAL mode and `BEGIN IMMEDIATE` on the booking path are part of how concurrent Retell retries stay serialized.

Timestamps are ISO-8601 UTC text. Public IDs are stable strings (`SLOT-001`, `APT-001`), not autoincrement integers. Fictional patient names only: no phone, email, medical, or payment columns.

ER diagram (product target)

```mermaid
erDiagram
    appointment_slot ||--o{ appointment : holds
    appointment ||--o| idempotency_record : "locked by"
    appointment ||--o{ request_event : evidenced_by
    idempotency_record ||--o{ request_event : correlated_with

    appointment_slot {
        text id PK "SLOT-001"
        text dentist_name
        text starts_at "ISO-8601 UTC"
        text ends_at "ISO-8601 UTC"
        text status "available | occupied"
    }

    appointment {
        text id PK "APT-001"
        text slot_id FK
        text patient_name "fictional only"
        text status "active"
        text created_at
    }

    idempotency_record {
        text key PK "derived call_id + booking"
        text request_fingerprint "canonical payload hash"
        text appointment_id FK
        text created_at
    }

    request_event {
        int id PK "internal"
        text created_at
        int attempt_number
        text event_type
        text outcome
        text appointment_id FK "nullable"
        text idempotency_key "nullable"
        text call_id "sanitized; nullable"
    }
```

Invariants the schema must enforce, including under overlapping requests:

- `idempotency_record.key` is unique.
- At most one `appointment` with `status = 'active'` per `slot_id` (partial unique index).
- `appointment.slot_id` references `appointment_slot.id` (`ON DELETE RESTRICT`).
- `idempotency_record.appointment_id` references `appointment.id` (`ON DELETE RESTRICT`).

`appointment_slot.status` is the flag availability and the dashboard read. The partial unique index is the booking lock. Both change in the same transaction.

Quick reference

| Table | Purpose |
| --- | --- |
| `appointment_slot` | Deterministic dental schedule. Stable IDs and start times the agent can speak. Seed occupied rows need no appointment; demo bookings flip `available` → `occupied`. |
| `appointment` | A created booking. Public ID returned to Retell and shown on the dashboard. Version one never reschedules or cancels, so `status` stays `active`. |
| `idempotency_record` | One row per derived key. Same key + same fingerprint returns the original appointment. Same key + different fingerprint is a conflict. This is the duplicate-prevention lock, not an audit log. |
| `request_event` | Sanitized evidence timeline. Many rows per call: receipt, idempotency decision, appointment result, response outcome (including `created_then_response_delayed` and replay). Dashboard result is computed from these rows. |

slot vs appointment vs idempotency_record vs request_event: a **slot** is a time on the fictional calendar; an **appointment** is the booking that occupies one slot; an **idempotency_record** is the business lock that makes a retry return `APT-001` instead of inserting `APT-002`; a **request_event** is one inspectable step in the demo timeline. The unique key prevents duplicates. The event log explains that it happened.

## Demo seed schedule

One fictional dentist, **Dr. Elena Voss**, with 30-minute slots on **Monday 14 September 2026** and **Tuesday 15 September 2026**. Times are stored as UTC and spoken using the same clock values (`14:00` is "2:00 PM"). Occupied seed rows have no `appointment` row; they represent the clinic's pre-existing book.

| Slot ID | Starts (UTC) | Ends (UTC) | Status |
| --- | --- | --- | --- |
| SLOT-001 | 2026-09-14T14:00:00Z | 2026-09-14T14:30:00Z | occupied |
| SLOT-002 | 2026-09-14T14:30:00Z | 2026-09-14T15:00:00Z | available |
| SLOT-003 | 2026-09-14T15:00:00Z | 2026-09-14T15:30:00Z | available |
| SLOT-004 | 2026-09-14T15:30:00Z | 2026-09-14T16:00:00Z | occupied |
| SLOT-005 | 2026-09-15T14:00:00Z | 2026-09-15T14:30:00Z | available |
| SLOT-006 | 2026-09-15T14:30:00Z | 2026-09-15T15:00:00Z | occupied |
| SLOT-007 | 2026-09-15T15:00:00Z | 2026-09-15T15:30:00Z | available |
| SLOT-008 | 2026-09-15T15:30:00Z | 2026-09-15T16:00:00Z | available |

`POST /api/demo/reset` deletes demo-created `appointment`, `idempotency_record`, and `request_event` rows and restores exactly this table. The endpoint returns 403 when `LIVE_DEMO_ENABLED=false` so a paused public deployment keeps its captured demonstration. Agent configuration (task 011) should describe this same dentist, date range, and clock times.
