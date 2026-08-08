"""Backfill public browse fields so GET /v1/tickets/public can return items.

Idempotent: only fills missing public* attributes for tickets that have a
description and location label. Safe for local/dev DynamoDB repair.
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


def _category_for_public(item: dict) -> str | None:
    final = (item.get("finalCategory") or "").strip()
    if final and final != "PENDING_CLASSIFICATION":
        return final
    category = (item.get("category") or "").strip()
    if category and category != "PENDING_CLASSIFICATION":
        return category
    # Prefer a real category; fall back so older demo rows still appear publicly.
    return final or category or None


def backfill(*, dry_run: bool = False) -> int:
    settings = get_settings()
    table_name = build_table_name(settings.dynamodb_table_prefix, "tickets")
    table = create_dynamodb_resource(settings).Table(table_name)
    updated = 0
    scan_kwargs: dict = {}

    while True:
        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            description = (item.get("description") or "").strip()
            address = ((item.get("location") or {}).get("addressText") or "").strip()
            category = _category_for_public(item)
            if not description or not address or not category:
                continue

            if (
                item.get("publicStatus") == PUBLIC_TICKET_STATUS_PUBLISHED
                and item.get("publicDescription")
                and item.get("publicLocationLabel")
                and item.get("publicPublishedAt")
                and item.get("publicSortKey")
                and item.get("finalCategory")
            ):
                continue

            published_at = (
                item.get("publicPublishedAt")
                or item.get("updatedAt")
                or item.get("createdAt")
            )
            draft = {
                **item,
                "finalCategory": item.get("finalCategory") or category,
                "publicStatus": PUBLIC_TICKET_STATUS_PUBLISHED,
                "publicDescription": item.get("publicDescription") or description,
                "publicLocationLabel": item.get("publicLocationLabel") or address,
                "publicPublishedAt": published_at,
            }
            ticket = StoredTicket.model_validate(draft)
            sort_key = build_public_sort_key(ticket)

            print(
                f"{'DRY-RUN ' if dry_run else ''}publish {item.get('ticketNumber')} "
                f"category={ticket.final_category}"
            )
            if dry_run:
                updated += 1
                continue

            table.update_item(
                Key={"ticketId": item["ticketId"]},
                UpdateExpression=(
                    "SET finalCategory = :finalCategory, "
                    "publicStatus = :publicStatus, "
                    "publicDescription = :publicDescription, "
                    "publicLocationLabel = :publicLocationLabel, "
                    "publicPublishedAt = :publicPublishedAt, "
                    "publicSortKey = :publicSortKey"
                ),
                ExpressionAttributeValues={
                    ":finalCategory": ticket.final_category,
                    ":publicStatus": PUBLIC_TICKET_STATUS_PUBLISHED,
                    ":publicDescription": ticket.public_description,
                    ":publicLocationLabel": ticket.public_location_label,
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
    parser = argparse.ArgumentParser(description="Backfill public ticket browse fields.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    count = backfill(dry_run=args.dry_run)
    print(f"Done. Updated {count} ticket(s).")


if __name__ == "__main__":
    main()
