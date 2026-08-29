# Staff assistant

`POST /v1/staff-assistant/query` is a read-only, staff-Bearer-protected endpoint.
The staff dashboard assistant panel (#42) must call this endpoint; mock answers
are not accepted. The query is rate-limited by
`RATE_LIMIT_STAFF_ASSISTANT_LIMIT` / `_WINDOW_SECONDS` (default 30 / 60s).
It uses no model provider, network call, prompt, or client-supplied ticket data.
Every count and ticket reference is derived from persisted tickets after staff
browse scope and `staff_can_access_ticket` enforce municipality, department, and
role.

## Intents

Deterministic intents (English, Arabic, French, and mixed-language terms):

- high-priority / urgent / critical operational-queue summary
- repeated-problem area summary

Unsupported, negated, or constrained questions return bounded guidance with zero
references.

## Priority summary

Includes open tickets (`SUBMITTED`, `UNDER_REVIEW`, `ASSIGNED`, `IN_PROGRESS`)
with priority `high` or `critical`. `RESOLVED` and `CLOSED` are excluded.

The payload includes `count`, `asOf`, `categories`, `statuses`, `departments`,
and up to 20 ticket references ordered by actionability: overdue SLA, then
due-soon, then critical before high, then oldest `createdAt`, then `ticketId`.
`incompleteCount` covers tickets still at `PENDING_CLASSIFICATION`.

Drill-down uses `appliedFilters` keys that `GET /v1/tickets` accepts:
`urgency=high,critical` (comma-separated subset of `low|medium|high|critical`) and
`openOnly=true`. Ticket references stay capped at 20; the list API is the
complete drill-down when `count` is larger.

## Repeated-area summary

Grouping uses persisted coordinates only, never citizen `addressText` and never
invented neighborhood names.

- Cell size: **0.002 degrees** (~200m), implemented as `floor(coord * 500)` so the
  code never divides by binary-inexact `0.002`. South/west edges are inclusive;
  north/east are exclusive. Cell id: `{south:.3f},{west:.3f}` (for example
  `33.896,35.478`).
- `PLACEHOLDER` locations are **unlocated** and omitted from clusters
  (`unlocatedCount`).
- A cell is a repeated area only when it contains **at least two distinct
  reports**. Tickets that share `duplicateGroupId` count as **one** report.
  Ungrouped tickets count separately. Clusters expose `duplicateGroupCount` and
  `separateReportCount` so the dashboard can tell merged duplicates from nearby
  independent reports.
- Safe label: the most common staff `publicLocationLabel` in the cell, otherwise
  `Unlabeled cell {cellId}`. Equal counts break ties by case-insensitive then
  exact lexicographic order so the label does not depend on scan order.
- `areaClusters` is capped at **20** cells (highest distinct-report count, then
  `cellId`). Each cluster keeps exact `ticketCount` but at most **20** `ticketIds`.
  `areaClusterTotal` / `areaClustersTruncated` and `ticketIdsTruncated` tell the
  dashboard when the sample is incomplete. `appliedFilters` includes
  `maxAreaClusters` and `maxTicketIdsPerCluster`.

## Safety

Responses never include contact data, image keys, ticket descriptions, exact
private addresses, internal notes, account/session fields, prompts, or provider
output.

Run the regression coverage with:

```bash
cd backend
python -m pytest tests/test_staff_assistant.py -q
```
