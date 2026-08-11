"""Backfill staff collection GSI keys on existing ticket items (issue #267).

DynamoDB GSIs are sparse: rows without ``staffScopeKey``, ``staffSortKey``, and
``adminBrowseKey`` are invisible to ``GET /v1/tickets``, ``/map``, and
``/aggregates`` after the indexed collection path is enabled.

This script is idempotent and resumable. Safe deploy order:

1. ``make db-migrate`` (or ``python scripts/db/migrate.py``) so the staff GSIs exist
2. ``python scripts/db/backfill_staff_ticket_keys.py --dry-run`` then without ``--dry-run``
3. Verify sample tickets appear under staff list/map/aggregates
4. Route traffic to the indexed collection path

Resume a interrupted run with ``--exclusive-start-key '<LastEvaluatedKey JSON>'``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

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


def _needs_backfill(item: dict[str, Any], ticket: StoredTicket) -> bool:
    expected_scope = build_staff_scope_key(ticket)
    expected_sort = build_staff_sort_key(ticket)
    return (
        item.get(STAFF_SCOPE_KEY) != expected_scope
        or item.get(STAFF_SORT_KEY) != expected_sort
        or item.get(ADMIN_BROWSE_KEY) != ADMIN_BROWSE_ALL
    )


def backfill(
    *,
    dry_run: bool = False,
    exclusive_start_key: dict[str, Any] | None = None,
    max_items: int | None = None,
) -> tuple[int, dict[str, Any] | None]:
    """Return (updated_count, last_evaluated_key_for_resume)."""
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
        for item in response.get("Items", []):
            scanned += 1
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
            if dry_run:
                if max_items is not None and updated >= max_items:
                    return updated, last_key
                continue

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
                return updated, last_key

        if not last_key:
            break
        if max_items is not None and updated >= max_items:
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
        help="Stop after updating this many tickets (still prints resume key).",
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
