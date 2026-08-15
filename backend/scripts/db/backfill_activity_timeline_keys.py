"""Idempotently backfill chronological activity keys for the timeline GSIs."""

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

TABLES = {
    "status": ("ticket-status-history", "historyId", "status"),
    "audit": ("ticket-audit-history", "auditId", "audit"),
    "comments": ("staff-comments", "commentId", "comment"),
}


def backfill_table(
    table: Any,
    *,
    id_field: str,
    kind: str,
    dry_run: bool,
    exclusive_start_key: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    scan_kwargs: dict[str, Any] = {}
    if exclusive_start_key:
        scan_kwargs["ExclusiveStartKey"] = exclusive_start_key
    updated = 0
    while True:
        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            item_id = item.get(id_field)
            created_at = item.get("createdAt")
            if not isinstance(item_id, str) or not isinstance(created_at, str):
                continue
            expected = f"{created_at}#{kind}:{item_id}"
            if item.get("timelineKey") == expected:
                continue
            updated += 1
            if not dry_run:
                table.update_item(
                    Key={id_field: item_id},
                    UpdateExpression="SET timelineKey = :timelineKey",
                    ExpressionAttributeValues={":timelineKey": expected},
                )
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            print(f"{kind}: updated {updated} item(s)")
            return None
        scan_kwargs["ExclusiveStartKey"] = last_key


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--table", choices=tuple(TABLES), default=None)
    parser.add_argument("--exclusive-start-key", default=None)
    args = parser.parse_args()
    start_key = json.loads(args.exclusive_start_key) if args.exclusive_start_key else None
    settings = get_settings()
    resource = create_dynamodb_resource(settings)
    selected = [args.table] if args.table else list(TABLES)
    for name in selected:
        suffix, id_field, kind = TABLES[name]
        resume = backfill_table(
            resource.Table(build_table_name(settings.dynamodb_table_prefix, suffix)),
            id_field=id_field,
            kind=kind,
            dry_run=args.dry_run,
            exclusive_start_key=start_key if name == args.table else None,
        )
        if resume:
            print(f"Resume {name} with --table {name} --exclusive-start-key '{json.dumps(resume)}'")


if __name__ == "__main__":
    main()
