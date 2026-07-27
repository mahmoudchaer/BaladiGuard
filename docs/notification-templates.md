# Notification Message Templates (MVP v1)

This document defines reusable citizen-facing notification templates for BaladiGuard.

It is the contract for issue **#40**. Issue **#39** consumes these templates through a
notification adapter and must not hard-code alternate message wording for the same events.

Templates render text only. They do not send SMS/email and do not talk to AWS SNS/SES.

## Events

| Event key | When to use | Default status |
| --- | --- | --- |
| `ticket_created` | After a citizen report is accepted | `SUBMITTED` |
| `ticket_updated` | After an important non-resolved status change | caller supplies status |
| `ticket_resolved` | After the ticket reaches `RESOLVED` or `CLOSED` | `RESOLVED` |

## Status validation

All render helpers **fail closed** on unknown statuses (`ValueError`). They never
silently substitute a default status when the caller passes an invalid value.

Additional event rules:

- `ticket_updated` rejects terminal statuses (`RESOLVED`, `CLOSED`) — use
  `ticket_resolved` instead.
- `ticket_resolved` accepts only `RESOLVED` and `CLOSED`.

## Required fields

Every rendered message includes:

| Field | Description |
| --- | --- |
| `ticketId` | Stable ticket identifier |
| `status` | Workflow status enum |
| `statusText` | Short human-readable status label |
| `subject` | One-line notification title |
| `body` | Short message body |

Optional enrichments:

| Field | Description |
| --- | --- |
| `ticketNumber` | Citizen-friendly number shown beside the ticket ID when available |
| `trackingCode` | Appended to the body when available |

## Status text map

| Status | Short status text |
| --- | --- |
| `SUBMITTED` | Submitted |
| `UNDER_REVIEW` | Under Review |
| `ASSIGNED` | Assigned |
| `IN_PROGRESS` | In Progress |
| `RESOLVED` | Resolved |
| `CLOSED` | Closed |

## Template wording

### Ticket created

```text
Subject: BaladiGuard: ticket {ticketNumber} ({ticketId}) created
Body: Your BaladiGuard report {ticketNumber} ({ticketId}) was created. Status: Submitted. Tracking code: {trackingCode}.
```

If `ticketNumber` is missing, use `{ticketId}` alone. If `trackingCode` is missing, omit the
tracking sentence.

### Ticket updated

```text
Subject: BaladiGuard: ticket {ticketNumber} ({ticketId}) updated
Body: Your BaladiGuard report {ticketNumber} ({ticketId}) was updated. Status: {statusText}.
```

### Ticket resolved

```text
Subject: BaladiGuard: ticket {ticketNumber} ({ticketId}) resolved
Body: Your BaladiGuard report {ticketNumber} ({ticketId}) was resolved. Status: Resolved.
```

For `CLOSED`, wording uses “closed” instead of “resolved”:

```text
Subject: BaladiGuard: ticket {ticketNumber} ({ticketId}) closed
Body: Your BaladiGuard report {ticketNumber} ({ticketId}) was closed. Status: Closed.
```

## Runtime source of truth

- Module: `backend/app/services/notifications/templates.py`
- Exports: `render_ticket_created`, `render_ticket_updated`, `render_ticket_resolved`,
  `render_notification`
- Tests: `backend/tests/test_notification_templates.py`

## Out of scope for #40

- Delivery adapters / SNS / SES / SMS providers → issue **#39**
- Triggering notifications from ticket create/status endpoints → issue **#39**
- Idempotency / failure logging around delivery → issue **#39**
- Multilingual template localization → later sprint

When changing wording, update this document and the template module/tests in the same PR.
