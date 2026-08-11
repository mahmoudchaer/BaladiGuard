"""Backfill staff collection GSI keys on existing ticket items (issue #267).

DynamoDB GSIs are sparse: rows without ``staffScopeKey``, ``staffSortKey``, and
``adminBrowseKey`` are invisible to ``GET /v1/tickets``, ``/map``, and
``/aggregates`` after the indexed collection path is enabled.

This script is idempotent and resumable. Safe deploy order:

1. ``make db-migrate`` (or ``python scripts/db/migrate.py``) so the staff GSIs exist
2. ``python scripts/db/backfill_staff_ticket_keys.py --dry-run`` then without ``--dry-run``
3. Verify sample tickets appear under staff list/map/aggregates
4. Route traffic to the indexed collection path

Resume an interrupted run with ``--exclusive-start-key '<LastEvaluatedKey JSON>'``.

``--max-items`` is a soft stop: the current scan page is always finished before a
resume key is emitted, so checkpoints never skip remaining items on that page.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Protocol

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import (
    ADMIN_BROWSE_ALL,
    ADMIN_BROWSE_KEY,
    STAFF_SCOPE_KEY,
    STAFF_SORT_KEY,
    build_staff_scope_key,
    build_staff_sort_key,
)
from app.schemas.stored_ticket import StoredTicket


class _TicketTable(Protocol):
    def scan(self, **kwargs: Any) -> dict[str, Any]: ...

    def update_item(self, **kwargs: Any) -> dict[str, Any]: ...


def _needs_backfill(item: dict[str, Any], ticket: StoredTicket) -> bool:
    expected_scope = build_staff_scope_key(ticket)
    expected_sort = build_staff_sort_key(ticket)
    return (
        item.get(STAFF_SCOPE_KEY) != expected_scope
        or item.get(STAFF_SORT_KEY) != expected_sort
        or item.get(ADMIN_BROWSE_KEY) != ADMIN_BROWSE_ALL
    )


def _process_scan_page(
    items: list[dict[str, Any]],
    *,
    dry_run: bool,
    max_items: int | None,
    updated: int,
    table: _TicketTable | None,
) -> tuple[int, bool]:
    """Process one scan page. Returns (updated_count, stop_after_this_page).

    When ``max_items`` is reached mid-page, remaining items on the page are still
    processed so a resume key aligned to ``LastEvaluatedKey`` cannot skip them.
    """
    stop_after_page = False
    for item in items:
        ticket_id = item.get("ticketId")
        if not isinstance(ticket_id, str):
            continue
        try:
            ticket = StoredTicket.model_validate(item)
        except Exception as exc:  # noqa: BLE001 - continue past corrupt rows
            print(f"skip {ticket_id}: {type(exc).__name__}: {exc}")
            continue

        if not _needs_backfill(item, ticket):
            continue

        scope_key = build_staff_scope_key(ticket)
        sort_key = build_staff_sort_key(ticket)
        print(
            f"{'DRY-RUN ' if dry_run else ''}backfill-staff-keys {ticket.ticket_number} "
            f"scope={scope_key}"
        )
        updated += 1
        if not dry_run:
            assert table is not None
            table.update_item(
                Key={"ticketId": ticket_id},
                UpdateExpression=(
                    f"SET {STAFF_SCOPE_KEY} = :scope, "
                    f"{STAFF_SORT_KEY} = :sort, "
                    f"{ADMIN_BROWSE_KEY} = :browse"
                ),
                ExpressionAttributeValues={
                    ":scope": scope_key,
                    ":sort": sort_key,
                    ":browse": ADMIN_BROWSE_ALL,
                },
            )
        if max_items is not None and updated >= max_items:
            stop_after_page = True
            # Keep processing the rest of this page; do not return mid-page.
    return updated, stop_after_page


def backfill(
    *,
    dry_run: bool = False,
    exclusive_start_key: dict[str, Any] | None = None,
    max_items: int | None = None,
    table: _TicketTable | None = None,
) -> tuple[int, dict[str, Any] | None]:
    """Return (updated_count, last_evaluated_key_for_resume)."""
    if table is None:
        settings = get_settings()
        table_name = build_table_name(settings.dynamodb_table_prefix, "tickets")
        table = create_dynamodb_resource(settings).Table(table_name)

    updated = 0
    scanned = 0
    scan_kwargs: dict[str, Any] = {}
    if exclusive_start_key:
        scan_kwargs["ExclusiveStartKey"] = exclusive_start_key

    last_key: dict[str, Any] | None = None
    while True:
        response = table.scan(**scan_kwargs)
        last_key = response.get("LastEvaluatedKey")
        page_items = list(response.get("Items", []))
        scanned += len(page_items)
        updated, stop_after_page = _process_scan_page(
            page_items,
            dry_run=dry_run,
            max_items=max_items,
            updated=updated,
            table=None if dry_run else table,
        )

        if not last_key:
            break
        if stop_after_page:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    print(f"Scanned {scanned} item(s).")
    return updated, last_key


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill staffScopeKey/staffSortKey/adminBrowseKey on tickets."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--exclusive-start-key",
        default=None,
        help="Resume from a prior LastEvaluatedKey JSON object.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help=(
            "Soft stop after at least this many updates; the current scan page "
            "is always finished before emitting a resume key."
        ),
    )
    args = parser.parse_args()
    start_key = None
    if args.exclusive_start_key:
        start_key = json.loads(args.exclusive_start_key)
        if not isinstance(start_key, dict):
            raise SystemExit("--exclusive-start-key must be a JSON object")

    count, resume_key = backfill(
        dry_run=args.dry_run,
        exclusive_start_key=start_key,
        max_items=args.max_items,
    )
    print(f"Done. Updated {count} ticket(s).")
    if resume_key:
        print("Resume with:")
        print(
            "  python scripts/db/backfill_staff_ticket_keys.py "
            f"--exclusive-start-key '{json.dumps(resume_key, separators=(',', ':'))}'"
        )


if __name__ == "__main__":
    main()
