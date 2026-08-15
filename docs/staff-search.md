# Staff global search

`GET /v1/staff-search?q=` is a read-only, staff-Bearer-protected search across
approved operational records. It is the backend for the dashboard global search
(#42 / #260). Mock or client-side full-record scans are not accepted.

## Query rules

| Rule | Value |
| --- | --- |
| Minimum length | 2 characters after trim |
| Maximum length | 80 characters |
| Normalization | trim, collapse internal whitespace, case-insensitive match |
| Ticket / tracking references | ticket id (`tkt_…`), ticket number (`BG-YYYY-####`), tracking code (spaces ignored) |
| Results per type | 8 |
| Ticket scan budget | 200 most recent scoped staff tickets |

Rate limit: `RATE_LIMIT_STAFF_SEARCH_LIMIT` / `_WINDOW_SECONDS` (default 40 / 60s),
keyed by client identity plus staff id.

## Approved fields

Search matches only:

- Tickets: `ticketId`, `ticketNumber`, `trackingCode`, `publicLocationLabel`
- Workers: `workerId`, `displayName`
- Teams: `teamId`, `displayName`
- Work orders: `workOrderId`, `state`, staff `summary`, plus the parent ticket number

Citizen phone, email, full name, private comments, private images, raw
`addressText`, and ticket descriptions are not searchable and never returned.

## Authorization

Every hit is filtered with the same municipality / department / role rules as
staff ticket and workforce reads. Inaccessible tickets and work orders attached
to inaccessible tickets are omitted, not 404'd.

## Response

Grouped arrays: `tickets`, `workers`, `teams`, `workOrders`. Each group exposes
`truncated` when more than 8 matches existed. `scanTruncated` is true when the
ticket budget was exhausted. `partialFailures` lists `tickets`, `work_orders`,
or `workforce` when that group failed independently so the UI can show the
remaining groups.

`limits` repeats the documented caps so the dashboard can explain incomplete
results.

## Drill-down filters

Assistant and search quick actions navigate with structured query params only:

- `urgency`, `openOnly`, `status`, `category`, `departmentId`, `slaState`
- `ticketIds` (max 20 operational ids) for cluster/list samples
- map `south`, `west`, `north`, `east`, `zoom`
- `workerId` / `teamId` on `/workforce`

Private text, questions, contacts, and image keys must never be copied into URLs.

Run:

```bash
cd backend
python -m pytest tests/test_staff_search.py tests/test_staff_assistant.py -q
```
