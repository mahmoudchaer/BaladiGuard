# Notification Delivery (issues #39 / #40 / #183)

BaladiGuard emits citizen notifications for important ticket lifecycle events.
Templates come from issue **#40**. This document covers the **delivery** layer
(mock MVP and real SES email + SNS SMS).

## Architecture

```text
ticket create / status update
        │
        ▼
emit_ticket_notification()
        │
        ├─ idempotency ledger (memory claim, or DynamoDB conditional claim)
        ├─ render_notification()  (#40 templates)
        ├─ NotificationAdapter.deliver()  (mock | SES+SNS)
        └─ delivery records (memory or DynamoDB)
```

Ticket create/status **never** roll back when delivery fails. Failures are logged
and, when available, recorded as safe delivery metadata (no message body, no full contact when redacted).

## Adapter interface

| Piece | Role |
| --- | --- |
| `NotificationAdapter` | Protocol with `mode` (`mock` \| `real`) and `deliver(message, recipient)` → channel results |
| `MockNotificationAdapter` | Default — logs **mock** delivery (not SMS/email) |
| `AwsSesSnsNotificationAdapter` | Real path: Amazon SES (email) + SNS (SMS) |
| `UnconfiguredRealNotificationAdapter` | `NOTIFICATION_ADAPTER=real` with no SES and SMS-only disabled; fails closed |
| `NotificationRecipient` | Optional phone/email/preferred channel for this event |

Sources:

- `backend/app/services/notifications/adapters.py`
- `backend/app/services/notifications/aws_adapter.py`
- `backend/app/services/notifications/service.py`

## Event payload

Each emit includes:

| Field | Source |
| --- | --- |
| `ticketId` | Ticket |
| `trackingCode` | Ticket (when present; also appears in rendered body) |
| `status` / event | New workflow status; event is `ticket_created`, `ticket_updated`, or `ticket_resolved` |
| recipient | Account-linked tickets use the current citizen profile preference; legacy unowned tickets use the ticket contact snapshot |

## Citizen notification preferences

Issue **#177** connects citizen profile preferences to the existing delivery flow. The templates,
adapter contract, idempotency ledger, and failure isolation above remain unchanged.

For tickets with `ownerUserId`, each ticket create/status notification resolves the owner profile at
send time:

| `notificationPreferences.ticketUpdates` | Delivery behavior |
| --- | --- |
| `SMS` | Send to the profile phone only |
| `EMAIL` | Send to the profile email only; skip if email is missing |
| `BOTH` | Send with profile phone and email when available |
| `NONE` | Skip delivery |

If the owner profile is missing or inactive, delivery is skipped without failing the ticket action.
Tickets without `ownerUserId` keep the pre-account behavior and deliver from the immutable ticket
contact snapshot when it contains phone and/or email.

## Idempotency and retry policy

Delivery claims the key `{event}:{ticketId}:{status}` **before** provider calls:

| Backend | Claim mechanism |
| --- | --- |
| Memory (`DATABASE_BACKEND=memory`) | Process-local in-memory set (single API process / local CI) |
| DynamoDB | Conditional `put_item` on table suffix `notification-claims` (`attribute_not_exists(idempotencyKey)`) so multiple workers cannot both send the same notification |

Delivery attempt rows (`notification-deliveries`) are written after the attempt for ops/audit; they are **not** the uniqueness authority.

| Outcome | Ledger claim | Notes |
| --- | --- | --- |
| Success (any channel sent or sandbox-only skip recorded) | Kept | Retries of the same event/status are skipped |
| Permanent failure (invalid recipient, provider reject, not configured) | Kept | Avoids retry storms; record stored when available |
| Transient failure (throttle, provider 5xx/timeout) | Released | A later emit may succeed |
| Unexpected exception | Released | Log and return false |

Status workflow already rejects same→same transitions, which also limits accidental repeats.

## Real delivery (SES + SNS)

When `NOTIFICATION_ADAPTER=real` and credentials/region are valid:

| Channel | Provider | Requirements |
| --- | --- | --- |
| Email | Amazon SES `SendEmail` | Verified `SES_FROM_EMAIL` (identity/domain) |
| SMS | Amazon SNS `Publish` to phone (E.164) | Account SMS enabled; optional `SNS_SMS_SENDER_ID` |

**Sandbox (default on local/test/development):** only destinations on the allowlists are delivered.
Others become `SKIPPED_SANDBOX` (recorded, no provider call).

**Per-destination rate limit (process-local):** extra bursts become `SKIPPED_THROTTLED` (transient for retry).

**Partial success:** if at least one channel succeeds, the emit counts as success and keeps the claim.

**Security / cost:**

- Logs use redacted destination hints and provider message IDs — never secrets, passwords, or full bodies with staff data.
- SMS uses body only (no subject); long SMS bodies are truncated.
- OTP SMS is out of scope for this adapter (citizen OTP path is separate).
- SES/SNS are usage-based; use sandbox/allowlists before production enablement.

## Delivery records

Each channel attempt can be stored (table suffix `notification-deliveries` on DynamoDB):

- Identifiers: delivery id, idempotency key, event, ticket id, status, channel
- Outcome: attempt status, optional failure category, optional provider message id
- `destinationHint` redacted only

## Configuration

| Env var | Default | Meaning |
| --- | --- | --- |
| `NOTIFICATION_ADAPTER` | `mock` | `mock` \| `real` |
| `SES_FROM_EMAIL` | empty | Verified SES from address (required for email and for production fail-closed) |
| `SES_CONFIGURATION_SET` | empty | Optional SES configuration set name |
| `SNS_SMS_SENDER_ID` | empty | Optional SNS SMS sender id where supported |
| `NOTIFICATION_ALLOW_SMS_ONLY_REAL` | `true` | Allow real SMS without SES from-address |
| `NOTIFICATION_SANDBOX` | env-dependent | Default `true` for local/test/development; `false` when unset in production |
| `NOTIFICATION_ALLOWLIST_EMAILS` | empty | Comma-separated emails permitted in sandbox |
| `NOTIFICATION_ALLOWLIST_PHONES` | empty | Comma-separated E.164 phones permitted in sandbox |
| `NOTIFICATION_DESTINATION_RATE_LIMIT` | `10` | Max sends per destination per window |
| `NOTIFICATION_DESTINATION_RATE_WINDOW_SECONDS` | `60` | Throttle window |

Production validation requires `NOTIFICATION_ADAPTER=real` and `SES_FROM_EMAIL`. Leaving sandbox on in production is a **warning**.

See also [configuration.md](./configuration.md) and [cloud-setup.md](./cloud-setup.md).

## Triggers

| Workflow | Event |
| --- | --- |
| `POST /v1/tickets` success | `ticket_created` |
| `PATCH .../status` to non-terminal | `ticket_updated` |
| `PATCH .../status` to `RESOLVED` / `CLOSED` | `ticket_resolved` |

## Mock vs real

- Mock log lines include `mode=mock` and `Notification mock delivery`.
- Real mode uses SES/SNS when configured; otherwise the unconfigured adapter fails closed (ticket still succeeds).

## Tests

- `backend/tests/test_notifications.py` — mock adapter, preferences, recipient, idempotency, no ticket rollback
- `backend/tests/test_notification_aws_adapter.py` — SES/SNS fakes, sandbox, throttle, permanent/transient, records
- `backend/tests/test_notification_templates.py` — #40 wording
- `backend/tests/test_health.py` — emit never raises
