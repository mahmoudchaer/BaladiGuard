# Staff ticket collection (issue #267)

Indexed, cursor-paginated staff list / map / aggregates contracts replace the previous
full-table scan + N+1 history/S3 mapping path for dashboard collection views.

## DynamoDB index keys

On every ticket `put_item` (`ticket_to_item`):

| Attribute | Value |
| --- | --- |
| `staffScopeKey` | `municipalityId`, or `UNSCOPED` when municipality is null |
| `staffSortKey` | `{createdAt}#{ticketId}` (newest-first via `ScanIndexForward=False`) |
| `adminBrowseKey` | always `ALL` |

GSIs on `{prefix}tickets`:

| Index | HASH | RANGE |
| --- | --- | --- |
| `staffScopeKey-staffSortKey-index` | `staffScopeKey` | `staffSortKey` |
| `adminBrowseKey-staffSortKey-index` | `adminBrowseKey` | `staffSortKey` |
| `departmentId-staffSortKey-index` | `departmentId` | `staffSortKey` |

Administrators query `adminBrowseKey = ALL`. Municipal staff query
`staffScopeKey = <municipalityId>` (or the department index when a single
`departmentId` filter is supplied), then post-filter to the caller's department set
(including unassigned tickets).

**Unsupported filter combinations must not silently fall back to an unbounded table
scan.** Persist-field filters (`status`, `category`, `urgency`, `departmentId`,
`assignmentState`, `q`) use `FilterExpression` on the scoped query. Derived
`slaState` is applied in the service layer with bounded continue-fetch across source
pages until the requested page is filled or the source is exhausted (so aging/overdue
queues cannot return a false empty page).

## Safe deploy / backfill ordering

DynamoDB GSIs are **sparse**. Existing tickets written before these attributes existed
are invisible to the indexed collection path until rewritten.

1. Run `make db-migrate` (or `python scripts/db/migrate.py`) so the staff GSIs exist.
2. Dry-run then apply the idempotent backfill:
   ```bash
   cd backend
   python scripts/db/backfill_staff_ticket_keys.py --dry-run
   python scripts/db/backfill_staff_ticket_keys.py
   ```
   Resume an interrupted run with the printed `--exclusive-start-key` JSON.
   `--max-items` is a soft stop: the current scan page is always finished before a
   resume key is emitted, so checkpoints never skip remaining items on that page.
3. Verify sample tickets appear under staff list / map / aggregates.
4. Only then route production/staging reads through the indexed collection path.

New writes always set the staff keys via `ticket_to_item`.

## Cursors

Opaque URL-safe base64 JSON cursors. Memory encodes `{staffSortKey}`; Dynamo encodes
the GSI `ExclusiveStartKey` (including `ticketId` + index hash/range). Invalid cursors
return `400 VALIDATION_ERROR`.

Default page size is **25** (max **100**). Responses include `nextCursor`,
`scannedCount`, nullable `approximateTotal`, and `freshnessHintSeconds` (default 30).
`previousCursor` stays null because Dynamo ExclusiveStartKey cursors are forward-only;
the admin client keeps a cursor history stack for Previous navigation.

When a sparse `FilterExpression` exhausts the bounded query rounds while
`LastEvaluatedKey` remains, `nextCursor` is still returned so clients can continue
instead of treating the response as end-of-results.

## Collection filters

`GET /v1/tickets` accepts:

| Param | Notes |
| --- | --- |
| `status`, `category`, `urgency`, `departmentId` | Persist-field FilterExpression. `urgency` accepts one level or a comma-separated subset (`high,critical`). |
| `assignmentState` | `assigned` / `unassigned` |
| `q` | Bounded contains match on ticket number/id/description/address |
| `ticketIds` | Comma-separated operational ticket ids (max 20). Fetched by id; inaccessible or missing ids are omitted. |
| `slaState` | Derived; continue-fetch across source pages until filled |
| `limit`, `cursor` | Pagination |

Search and queue views (critical / high / unassigned / overdue) are sent as these
server filters — they are not client-only filters over the current page.

## Duplicate workspace reads (issue #269)

The staff page path is also the scan source for
`GET /v1/tickets/{ticketId}/duplicate-candidates`. That endpoint pages the scoped staff
list with `openOnly` and post-filters for the source's effective category, using the same
continue-fetch pattern as `slaState`: it keeps pulling source pages (bounded rounds) until
the requested page size is filled. When the page fills mid-scan it returns a continuation
cursor built from the last included ticket, so remaining matches on that source page are
never skipped. `GET /v1/tickets/{ticketId}/duplicate-comparison/{candidateTicketId}` is a
direct scoped read of both tickets. Both projections are bounded (no contact, tracking
code, `imageObjectKey`, history, AI blobs, or public drafts) and are documented in
`docs/MVP_API_CONTRACT.md`.

## Map viewport

`GET /v1/tickets/map` accepts `north`, `south`, `east`, `west`, `zoom`, the same
collection filters, and `limit` (default 200, max 500). Candidates are loaded through
the scoped staff page path with a bounded internal budget (500). Zoom **&lt; 14** (or
when in-bounds points would exceed `limit`) returns grid clusters; otherwise individual
markers. Markers omit contact, tracking codes, histories, and image URLs.

## Aggregates

`GET /v1/tickets/aggregates` returns scoped `openCount`, `criticalCount`, `highCount`,
`unassignedCount`, and `overdueCount`. Counts are exact when the scoped set fits the
sample budget; otherwise `approximate: true`.

## Admin client behavior

The admin dashboard:

- Loads `GET /v1/tickets` as a cursor page (`fetchTicketsPage`) with AbortController
  cancellation, debounced filter changes, soft refresh, and next-page prefetch.
- Caches pages in a bounded in-memory store keyed by staff scope + filters + cursor.
  Stale hits return immediately and expose a `revalidate` promise so the UI applies the
  fresh page when it arrives (guarded by request generation). Cache clears on logout /
  session clear / `401`.
- Maintains a cursor history stack for Previous / Next.
- Loads attention counts from `GET /v1/tickets/aggregates` and labels approximate counts.
- Loads the map from `GET /v1/tickets/map` for the visible bounds/zoom (clusters at wider
  zooms, markers when safe). An accessible marker list sits below the map.
- Mutations invalidate affected list cache entries; full detail / evidence remains on
  `GET /v1/tickets/{ticketId}`.
- Loads merge candidates from `GET /v1/tickets/{ticketId}/duplicate-candidates`
  (debounced server-side search, Load more via `nextCursor`) rather than filtering one
  ticket-list page, and reads each side-by-side comparison from
  `GET /v1/tickets/{ticketId}/duplicate-comparison/{candidateTicketId}`. Merging stays
  disabled until every selected candidate's comparison has loaded.
