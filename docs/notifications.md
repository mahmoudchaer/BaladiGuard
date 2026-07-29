# Notification Delivery (MVP / issue #39)

BaladiGuard emits citizen notifications for important ticket lifecycle events.
Templates come from issue **#40**. This document covers the **delivery** layer.

## Architecture

```text
ticket create / status update
        │
        ▼
emit_ticket_notification()
        │
        ├─ idempotency ledger (skip duplicates)
        ├─ render_notification()  (#40 templates)
        └─ NotificationAdapter.deliver()  (mock or real)
```

Ticket create/status **never** roll back when delivery fails. Failures are logged.

## Adapter interface

| Piece | Role |
| --- | --- |
| `NotificationAdapter` | Protocol with `mode` (`mock` \| `real`) and `deliver(message, recipient)` |
| `MockNotificationAdapter` | Default MVP adapter — logs **mock** delivery (not SMS/email) |
| `UnconfiguredRealNotificationAdapter` | Selected when `NOTIFICATION_ADAPTER=real` until SNS/SES is wired; fails closed |
| `NotificationRecipient` | Optional phone/email/preferred channel from the ticket contact |

Source: `backend/app/services/notifications/adapters.py`

## Event payload

Each emit includes:

| Field | Source |
| --- | --- |
| `ticketId` | Ticket |
| `trackingCode` | Ticket (when present; also appears in rendered body) |
| `status` / event | New workflow status; event is `ticket_created`, `ticket_updated`, or `ticket_resolved` |
| recipient | From ticket contact when phone and/or email exist |

## Idempotency

Delivery claims a process-local key `{event}:{ticketId}:{status}`.

- Successful delivery keeps the claim → retries of the same event/status are skipped.
- Failed delivery **releases** the claim → a later retry can deliver.
- Status workflow already rejects same→same transitions, which also limits accidental repeats.

## Configuration

| Env var | Default | Meaning |
| --- | --- | --- |
| `NOTIFICATION_ADAPTER` | `mock` | `mock` = log-only mock delivery; `real` = provider path (not configured yet) |

## Triggers

| Workflow | Event |
| --- | --- |
| `POST /v1/tickets` success | `ticket_created` |
| `PATCH .../status` to non-terminal | `ticket_updated` |
| `PATCH .../status` to `RESOLVED` / `CLOSED` | `ticket_resolved` |

## Mock vs real

- Log lines from the mock adapter always include `mode=mock` and `Notification mock delivery`.
- Selecting `real` without a provider raises `NotificationDeliveryError` (logged; ticket update still succeeds).

## Tests

- `backend/tests/test_notifications.py` — adapter success/failure, recipient, idempotency, no ticket rollback
- `backend/tests/test_notification_templates.py` — #40 wording
- `backend/tests/test_health.py` — emit never raises
