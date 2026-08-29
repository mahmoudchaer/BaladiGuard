# Internal staff comments and activity

Ticket comments and activity are staff-only operational records. They are never included in citizen
tracking, public ticket feeds, analytics exports, notification text, or general audit details.

Comments are append-only and are stored through the configured comment store: in-memory for local
development and a DynamoDB `staff-comments` table (with a `ticketId-index`) when DynamoDB is enabled.
Each comment records author, timestamp, text, and validated in-scope staff mentions. The audit trail
records only that a comment was added; it never copies comment text.

The protected activity endpoint merges status history, audit-only mutations, and comments. Status audit
copies are suppressed because status history is canonical. Workforce assignment, work-order lifecycle,
maintenance evidence, and resolution-feedback records appear using their audit action types, including
WORKFORCE_ASSIGN, WORK_ORDER_CREATE, WORK_ORDER_ASSIGN, WORK_ORDER_START, WORK_ORDER_COMPLETE,
WORK_ORDER_CANCEL, WORK_ORDER_EVIDENCE_ADD, RESOLUTION_FEEDBACK_SUBMIT, and
RESOLUTION_FEEDBACK_REVIEW.

Rows are ordered by (occurredAt, sourceReference, eventId) and use an opaque keyset cursor, so a new
event arriving between requests cannot shift the next page. Replayed audit/domain operations are
deduplicated by stable source reference. Actor IDs and protected workforce, work-order, evidence, and
image storage identifiers are never serialized; only safe staff display names, summaries, and approved
resolution outcome values are projected. Evidence photos remain available only through the authorized
evidence endpoint.

Deployment must follow this cutover. The sparse `ticketTimeline-index` hides any row that still
lacks `timelineKey`, so GSI reads stay off until backfill is complete and verified.

1. `make db-migrate` (or `python scripts/db/migrate.py`) creates the timeline GSIs and waits until
   they are ACTIVE.
2. Dry-run, then apply the idempotent backfill in bounded chunks:
   ```bash
   cd backend
   python scripts/db/backfill_activity_timeline_keys.py --dry-run
   python scripts/db/backfill_activity_timeline_keys.py --checkpoint-file /tmp/timeline-backfill.json --max-pages 20
   ```
   Repeat the apply command until it prints completion and removes the checkpoint file. Interrupted
   runs resume from that file. `--max-items` and `--max-seconds` are additional soft stops; the
   current scan page is always finished before a checkpoint is written.
3. Verify sample tickets still show pre-migration status, audit, and comment activity.
4. Only then set `ACTIVITY_TIMELINE_USE_GSI=true` and restart the API.

Until step 4 the API keeps a compatibility read over `ticketId-index`, so historical activity
cannot disappear during an incomplete backfill. After the flag is enabled, each page reads only
the chronological GSI and does not rescan the legacy index.

Administrators should treat this feature as internal coordination data and apply the municipality's
normal access, retention, and export policies before sharing it outside authorized staff.
