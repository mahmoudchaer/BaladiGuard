"""Repair public browse index fields for already-published tickets.

Idempotent and privacy-safe: only rebuilds ``publicSortKey`` (and fills a
missing ``publicPublishedAt`` from existing timestamps) for tickets that are
already ``PUBLISHED`` with staff-approved ``publicDescription`` and
``publicLocationLabel``.

Never promotes DRAFT/UNPUBLISHED rows, and never copies raw citizen
``description`` or exact ``location.addressText`` into public fields.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import PUBLIC_TICKET_STATUS_PUBLISHED, build_public_sort_key
from app.schemas.stored_ticket import StoredTicket


def backfill(*, dry_run: bool = False) -> int:
    settings = get_settings()
    table_name = build_table_name(settings.dynamodb_table_prefix, "tickets")
    table = create_dynamodb_resource(settings).Table(table_name)
    updated = 0
    scan_kwargs: dict = {}

    while True:
        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            if item.get("publicStatus") != PUBLIC_TICKET_STATUS_PUBLISHED:
                continue

            public_description = (item.get("publicDescription") or "").strip()
            public_location_label = (item.get("publicLocationLabel") or "").strip()
            final_category = (item.get("finalCategory") or "").strip()
            if not public_description or not public_location_label or not final_category:
                # Missing staff-approved projection — do not invent public copy.
                continue

            published_at = (
                item.get("publicPublishedAt") or item.get("updatedAt") or item.get("createdAt")
            )
            if not published_at:
                continue

            draft = {
                **item,
                "finalCategory": final_category,
                "publicStatus": PUBLIC_TICKET_STATUS_PUBLISHED,
                "publicDescription": public_description,
                "publicLocationLabel": public_location_label,
                "publicPublishedAt": published_at,
            }
            ticket = StoredTicket.model_validate(draft)
            sort_key = build_public_sort_key(ticket)

            if item.get("publicSortKey") == sort_key and item.get("publicPublishedAt"):
                continue

            print(
                f"{'DRY-RUN ' if dry_run else ''}repair-index {item.get('ticketNumber')} "
                f"category={ticket.final_category}"
            )
            if dry_run:
                updated += 1
                continue

            table.update_item(
                Key={"ticketId": item["ticketId"]},
                UpdateExpression=(
                    "SET publicPublishedAt = :publicPublishedAt, publicSortKey = :publicSortKey"
                ),
                ExpressionAttributeValues={
                    ":publicPublishedAt": ticket.public_published_at,
                    ":publicSortKey": sort_key,
                },
            )
            updated += 1

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    return updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Repair publicSortKey for already-published tickets."
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    count = backfill(dry_run=args.dry_run)
    print(f"Done. Updated {count} ticket(s).")


if __name__ == "__main__":
    main()
