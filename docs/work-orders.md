# Maintenance work orders and structured outcomes (issue #247)

The **ticket** stays the citizen-facing case. A **work order** is the private municipal
execution record used to queue, assign, start, complete, or cancel field work.

Issue #251 (structured resolution and rejection reasons) is implemented on the same
ticket status path. Completing a work order requires after-image evidence (#248) and
never resolves the citizen ticket.

## Work-order persistence

DynamoDB table suffix `work-orders` (prefix `baladiguard-` by default):

| Attribute | Notes |
| --- | --- |
| `workOrderId` | Primary key, `wo_<hex>` |
| `ticketId` | Source ticket; GSI `ticketId-index` |
| `municipalityId` | Copied from the ticket, else the staff municipality, else Beirut demo id |
| `departmentId` | Required; copied from the ticket |
| `state` | `QUEUED`, `ASSIGNED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED` |
| `summary` | Staff operational summary (max 500) |
| `assignedWorkerId` / `assignedTeamId` | Exclusive; uses the #245 directory |
| actor / timestamp fields | `createdBy`, `updatedBy`, `startedBy`, `completedBy`, `cancelledBy` and matching timestamps |

The ticket stores `activeWorkOrderId` while a work order is queued, assigned, or in
progress. Completed and cancelled work orders clear that pointer so a later work
order can be created.

DynamoDB enforces one active work order per ticket with a claim item
`wo_active_<ticketId>` in the same table. Create writes the work order, the claim,
and `ticket.activeWorkOrderId` in one transaction. Assign/start/complete/cancel use
conditional writes on the current `state` and `updatedAt`. Complete/cancel also
delete the claim and clear the ticket pointer in the same transaction so a partial
failure cannot leave the two tables inconsistent.

## Allowed work-order transitions

| Current | Allowed next |
| --- | --- |
| `QUEUED` | `ASSIGNED`, `IN_PROGRESS`, `CANCELLED` |
| `ASSIGNED` | `IN_PROGRESS`, `QUEUED`, `CANCELLED` |
| `IN_PROGRESS` | `COMPLETED`, `ASSIGNED`, `CANCELLED` |
| `COMPLETED` | terminal |
| `CANCELLED` | terminal |

`IN_PROGRESS` from `QUEUED` requires an assignee. Starting without a worker or team
is rejected.

## HTTP

Staff-only. Missing tickets and out-of-scope tickets return `404 TICKET_NOT_FOUND`.

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/v1/tickets/{ticketId}/work-orders` | Create. Retry is idempotent: an existing active work order is returned as `200` |
| `GET` | `/v1/tickets/{ticketId}/work-orders` | History for the ticket plus `activeWorkOrderId` |
| `GET` | `/v1/work-orders/{workOrderId}` | Single work order |
| `POST` | `/v1/work-orders/{id}/assign` | `#245` worker XOR team XOR `clear` |
| `POST` | `/v1/work-orders/{id}/start` | Moves work to `IN_PROGRESS` |
| `POST` | `/v1/work-orders/{id}/complete` | Requires ≥1 after image. Optional private `note`. Does **not** resolve the ticket |
| `POST` | `/v1/work-orders/{id}/cancel` | Requires `reasonCode` |

Create is allowed only for accepted tickets (`UNDER_REVIEW`, `ASSIGNED`, `IN_PROGRESS`)
that already have a catalog department. `SUBMITTED`, `RESOLVED`, and `CLOSED` are
rejected.

## Ticket synchronization

Work-order mutations never invent ticket statuses. When a work order is created or
assigned, the ticket is moved toward `ASSIGNED` only along
[documented ticket transitions](./MVP_API_CONTRACT.md#allowed-status-transitions).
Starting a work order moves the ticket toward `IN_PROGRESS` the same way
(`UNDER_REVIEW` → `ASSIGNED` → `IN_PROGRESS` when needed). The ticket is never moved
backward, and completion/cancel leave the citizen ticket status unchanged.

Assignment reuses `#245` eligibility: inactive, unknown, other-municipality, and
out-of-department workers or teams are rejected. A successful work-order assignment
also updates the ticket workforce fields so workload counts stay aligned.

## Structured ticket outcomes

`PATCH /v1/tickets/{ticketId}/status` now requires `reasonCode` for terminal moves:

| Transition | Kind | Required codes |
| --- | --- | --- |
| `IN_PROGRESS` → `RESOLVED` | resolution | `WORK_COMPLETED`, `TEMPORARY_FIX`, `NO_WORK_REQUIRED`, `REFERRED_EXTERNAL`, `DUPLICATE_RESOLVED` |
| `SUBMITTED` / `UNDER_REVIEW` → `CLOSED` | rejection | `OUT_OF_SCOPE`, `INSUFFICIENT_INFORMATION`, `DUPLICATE`, `INVALID_REPORT`, `CITIZEN_WITHDRAWN`, `SPAM` |
| `RESOLVED` → `CLOSED` | closure | `CONFIRMED_COMPLETE`, `ADMINISTRATIVE_CLOSE`, `NO_FURTHER_ACTION` |

Optional `note` remains a bounded private staff note (max 500). Closing an already
resolved ticket writes closure fields and **preserves** the resolution record.

Work-order cancel codes: `CREATED_IN_ERROR`, `NO_LONGER_NEEDED`, `UNABLE_TO_PERFORM`,
`DUPLICATE_WORK`.

### Citizen-safe wording

Citizens see only `outcomeMessage` on tracking reads. Codes and private notes never
leave staff responses. Legacy terminal tickets without reasons remain readable;
`outcome` / `outcomeMessage` are null and the status label is enough.

| Code | Citizen-safe message |
| --- | --- |
| `WORK_COMPLETED` | The reported issue has been resolved. |
| `TEMPORARY_FIX` | A temporary repair has been applied. |
| `NO_WORK_REQUIRED` | Inspection found no municipal work was required. |
| `REFERRED_EXTERNAL` | The report was referred to another authority. |
| `DUPLICATE_RESOLVED` | This report was resolved as a duplicate of an existing case. |
| `OUT_OF_SCOPE` | This report is outside municipal responsibility. |
| `INSUFFICIENT_INFORMATION` | There was not enough information to act on this report. |
| `DUPLICATE` | This report matches an existing case. |
| `INVALID_REPORT` | This report could not be accepted as a municipal issue. |
| `CITIZEN_WITHDRAWN` | The report was withdrawn. |
| `SPAM` | This report could not be processed. |
| `CONFIRMED_COMPLETE` | This report has been closed. |
| `ADMINISTRATIVE_CLOSE` | This report has been closed. |
| `NO_FURTHER_ACTION` | No further municipal action is planned. |

## Audit and activity

Work-order mutations append ticket audit actions `WORK_ORDER_CREATE`,
`WORK_ORDER_ASSIGN`, `WORK_ORDER_START`, `WORK_ORDER_COMPLETE`,
`WORK_ORDER_CANCEL`, and `WORK_ORDER_EVIDENCE_ADD` with the authenticated actor
and timestamp. Evidence and resolution-feedback audits never include image URLs
or private notes. The #246 activity timeline includes those events. Status
history remains the canonical ticket-status record; internal notes stay off
citizen tracking.

## Completion evidence (issue #248)

Authorized staff attach **before** and **after** images on an active work order.
Keys are generated server-side under `work-orders/evidence/v1/{ticketScope}/...`.
Clients cannot supply object keys. The ticket's original report photo is
associated as `ORIGINAL_REPORT` when the work order is created.

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/v1/work-orders/{id}/evidence?kind=BEFORE\|AFTER` | Multipart `file`. Same 5MB / JPEG-PNG-WebP rules as report photos |
| `GET` | `/v1/work-orders/{id}` and ticket work-order list | Staff-only `evidence[]` plus `afterImageCount` |

At least one **after** image is required before `POST .../complete`. A failed or
partial upload does not create an evidence record and cannot complete the work
order. Completion still does not resolve the citizen ticket.

## Citizen resolution verification (issue #261)

Only the authenticated owner of an account-linked `RESOLVED` ticket can submit
feedback: `CONFIRMED_FIXED` or `STILL_UNRESOLVED`, plus an optional private note
(max 500). Retry with the same payload is idempotent. Other citizens and public
tracking never receive the note or the submitter identity.

| Method | Path | Notes |
| --- | --- | --- |
| `GET`/`POST` | `/v1/citizen/me/tickets/{trackingCode}/resolution-feedback` | Owner only |
| `GET` | `/v1/tickets/{ticketId}/resolution-feedback` | Staff; includes the private note |
| `POST` | `/v1/tickets/{ticketId}/resolution-feedback/review` | `KEEP_RESOLVED` or `RETURN_IN_PROGRESS` |
| `GET` | `/v1/resolution-reviews` | Pending municipal review queue |

`STILL_UNRESOLVED` alerts the review queue and never silently reopens or
reassigns the ticket. Staff may explicitly return it to `IN_PROGRESS`. Closing a
resolved ticket is blocked until unresolved feedback is reviewed. A receipt
notification confirms the update without repeating the private note.
