# Staff assistant

`POST /v1/staff-assistant/query` is a read-only, staff-Bearer-protected endpoint.
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

Drill-down filters: `appliedFilters.priority=high,critical` and `openOnly=true`.

## Repeated-area summary

Grouping uses persisted coordinates only, never citizen `addressText` and never
invented neighborhood names.

- Cell size: **0.002 degrees** (~200m). South/west edges are inclusive; north/east
  are exclusive (`floor(coord / 0.002) * 0.002`).
- Cell id: `{south:.3f},{west:.3f}` (for example `33.896,35.478`).
- `PLACEHOLDER` locations are **unlocated** and omitted from clusters
  (`unlocatedCount`).
- A cell is a repeated area only when it contains **at least two distinct
  reports**. Tickets that share `duplicateGroupId` count as **one** report.
  Ungrouped tickets count separately. Clusters expose `duplicateGroupCount` and
  `separateReportCount` so the dashboard can tell merged duplicates from nearby
  independent reports.
- Safe label: the most common staff `publicLocationLabel` in the cell, otherwise
  `Unlabeled cell {cellId}`.

`areaClusters[]` carries cell bounds, category counts, and `ticketIds` for
map/list drill-down.

## Safety

Responses never include contact data, image keys, ticket descriptions, exact
private addresses, internal notes, account/session fields, prompts, or provider
output.

Run the regression coverage with:

```bash
cd backend
python -m pytest tests/test_staff_assistant.py -q
```
