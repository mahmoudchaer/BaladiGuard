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
scan.** Persist-field filters (`status`, `category`, `urgency`, `departmentId`) use
`FilterExpression` on the scoped query. Derived `slaState` is applied in the service
layer within the fetched page only.

## Cursors

Opaque URL-safe base64 JSON cursors. Memory encodes `{staffSortKey}`; Dynamo encodes
the GSI `ExclusiveStartKey` (including `ticketId` + index hash/range). Invalid cursors
return `400 VALIDATION_ERROR`.

Default page size is **25** (max **100**). Responses include `nextCursor`, optional
`previousCursor`, `scannedCount`, nullable `approximateTotal`, and
`freshnessHintSeconds` (default 30) for client cache revalidation.

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
  Entries honor `freshnessHintSeconds` (stale-while-revalidate) and clear on logout /
  session clear / `401`.
- Loads attention counts from `GET /v1/tickets/aggregates` and labels approximate counts.
- Loads the map from `GET /v1/tickets/map` for the visible bounds/zoom (clusters at wider
  zooms, markers when safe). An accessible marker list sits below the map.
- Mutations invalidate affected list cache entries; full detail / evidence remains on
  `GET /v1/tickets/{ticketId}`.

Run `make db-migrate` (or the established Dynamo table ensure path) so staff GSIs exist
before sending production/staging traffic through the indexed collection path.
