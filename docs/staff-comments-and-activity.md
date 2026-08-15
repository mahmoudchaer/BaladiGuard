# Internal staff comments and activity

Ticket comments and activity are staff-only operational records. They are never included in citizen
tracking, public ticket feeds, analytics exports, notification text, or general audit details.

Comments are append-only and are stored through the configured comment store: in-memory for local
development and a DynamoDB `staff-comments` table (with a `ticketId-index`) when DynamoDB is enabled.
Each comment records author, timestamp, text, and validated in-scope staff mentions. The audit trail
records only that a comment was added; it never copies comment text.

The activity endpoint merges status history, audit-only mutations, and comments. Status audit copies
are suppressed because status history is canonical. Work-order mutations from issue #247 appear as
`WORK_ORDER_CREATE`, `WORK_ORDER_ASSIGN`, `WORK_ORDER_START`, `WORK_ORDER_COMPLETE`, and
`WORK_ORDER_CANCEL`. Results are cursor-paginated and the dashboard
deduplicates events by stable event ID when loading additional pages.

Administrators should treat this feature as internal coordination data and apply the municipality's
normal access, retention, and export policies before sharing it outside authorized staff.
