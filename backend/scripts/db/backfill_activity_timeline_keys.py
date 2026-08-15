"""Backfill chronological activity keys for the timeline GSIs.

DynamoDB ``ticketTimeline-index`` is sparse: rows without ``timelineKey`` are
invisible to GSI reads. Safe deploy order:

1. ``make db-migrate`` (create/wait for the timeline GSIs to become ACTIVE)
2. ``python scripts/db/backfill_activity_timeline_keys.py --dry-run``
3. Apply in bounded chunks until every table reports complete
4. Verify sample tickets still show pre-migration activity
5. Only then set ``ACTIVITY_TIMELINE_USE_GSI=true``

Until step 5 the API keeps a compatibility read so legacy rows stay visible.

Each invocation is bounded by ``--max-pages``, ``--max-items``, and/or
``--max-seconds``. The current scan page is always finished before a checkpoint
is emitted, so resume keys never skip remaining items on that page. Pass
``--checkpoint-file`` to persist the latest key after every chunk.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Protocol

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.database.activity_timeline import build_timeline_key
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name

TABLES = {
    "status": ("ticket-status-history", "historyId", "status"),
    "audit": ("ticket-audit-history", "auditId", "audit"),
    "comments": ("staff-comments", "commentId", "comment"),
}


class _TimelineTable(Protocol):
    def scan(self, **kwargs: Any) -> dict[str, Any]: ...

    def update_item(self, **kwargs: Any) -> dict[str, Any]: ...


def expected_timeline_key(item: dict[str, Any], *, id_field: str, kind: str) -> str | None:
    item_id = item.get(id_field)
    created_at = item.get("createdAt")
    if not isinstance(item_id, str) or not isinstance(created_at, str):
        return None
    return build_timeline_key(kind, item_id, created_at)


def _process_scan_page(
    items: list[dict[str, Any]],
    *,
    id_field: str,
    kind: str,
    dry_run: bool,
    max_items: int | None,
    updated: int,
    table: _TimelineTable | None,
) -> tuple[int, bool]:
    stop_after_page = False
    for item in items:
        expected = expected_timeline_key(item, id_field=id_field, kind=kind)
        item_id = item.get(id_field)
        if expected is None or not isinstance(item_id, str):
            continue
        if item.get("timelineKey") == expected:
            continue
        updated += 1
        if not dry_run:
            assert table is not None
            table.update_item(
                Key={id_field: item_id},
                UpdateExpression="SET timelineKey = :timelineKey",
                ExpressionAttributeValues={":timelineKey": expected},
            )
        if max_items is not None and updated >= max_items:
            stop_after_page = True
    return updated, stop_after_page


def backfill_table(
    table: _TimelineTable,
    *,
    id_field: str,
    kind: str,
    dry_run: bool = False,
    exclusive_start_key: dict[str, Any] | None = None,
    max_items: int | None = None,
    max_pages: int | None = None,
    max_seconds: float | None = None,
    on_checkpoint: Any | None = None,
) -> tuple[int, dict[str, Any] | None]:
    """Return (updated_count, last_evaluated_key_for_resume)."""
    updated = 0
    scanned_pages = 0
    started = time.monotonic()
    scan_kwargs: dict[str, Any] = {}
    if exclusive_start_key:
        scan_kwargs["ExclusiveStartKey"] = exclusive_start_key

    last_key: dict[str, Any] | None = None
    while True:
        response = table.scan(**scan_kwargs)
        last_key = response.get("LastEvaluatedKey")
        page_items = list(response.get("Items", []))
        scanned_pages += 1
        updated, stop_after_page = _process_scan_page(
            page_items,
            id_field=id_field,
            kind=kind,
            dry_run=dry_run,
            max_items=max_items,
            updated=updated,
            table=None if dry_run else table,
        )
        if on_checkpoint is not None:
            on_checkpoint(last_key)
        if not last_key:
            return updated, None
        budget_exhausted = stop_after_page
        if max_pages is not None and scanned_pages >= max_pages:
            budget_exhausted = True
        if max_seconds is not None and (time.monotonic() - started) >= max_seconds:
            budget_exhausted = True
        if budget_exhausted:
            return updated, last_key
        scan_kwargs["ExclusiveStartKey"] = last_key


def load_checkpoint(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("--checkpoint-file must contain a JSON object")
    return payload


def save_checkpoint(path: Path | None, payload: dict[str, Any] | None) -> None:
    if path is None:
        return
    if payload is None:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def backfill(
    *,
    dry_run: bool = False,
    table_name: str | None = None,
    exclusive_start_key: dict[str, Any] | None = None,
    max_items: int | None = None,
    max_pages: int | None = None,
    max_seconds: float | None = None,
    checkpoint_file: Path | None = None,
    tables: dict[str, _TimelineTable] | None = None,
) -> tuple[int, dict[str, Any] | None]:
    """Backfill one or all tables. Returns (updated, checkpoint_or_none)."""
    checkpoint = load_checkpoint(checkpoint_file) or {}
    selected = [table_name] if table_name else list(TABLES)
    completed = list(checkpoint.get("completed") or [])
    current = table_name or checkpoint.get("table") or selected[0]
    start_key = exclusive_start_key
    if start_key is None and checkpoint.get("table") == current:
        start_key = checkpoint.get("exclusiveStartKey")

    if tables is None:
        settings = get_settings()
        resource = create_dynamodb_resource(settings)
        tables = {
            name: resource.Table(build_table_name(settings.dynamodb_table_prefix, suffix))
            for name, (suffix, _id_field, _kind) in TABLES.items()
        }

    updated = 0
    remaining = [name for name in selected if name not in completed]
    if current in remaining:
        remaining = [current, *[name for name in remaining if name != current]]

    for name in remaining:
        suffix, id_field, kind = TABLES[name]
        table = tables[name]

        def _persist_for(table_name: str):
            def _persist(last_key: dict[str, Any] | None) -> None:
                if last_key:
                    save_checkpoint(
                        checkpoint_file,
                        {
                            "table": table_name,
                            "exclusiveStartKey": last_key,
                            "completed": completed,
                        },
                    )

            return _persist

        remaining_items = None if max_items is None else max(0, max_items - updated)
        chunk_updated, resume_key = backfill_table(
            table,
            id_field=id_field,
            kind=kind,
            dry_run=dry_run,
            exclusive_start_key=start_key if name == current else None,
            max_items=remaining_items,
            max_pages=max_pages,
            max_seconds=max_seconds,
            on_checkpoint=_persist_for(name),
        )
        updated += chunk_updated
        start_key = None
        if resume_key:
            payload = {
                "table": name,
                "exclusiveStartKey": resume_key,
                "completed": completed,
            }
            save_checkpoint(checkpoint_file, payload)
            print(f"{kind}: updated {chunk_updated} item(s); paused with checkpoint")
            return updated, payload
        completed.append(name)
        payload = {"table": None, "exclusiveStartKey": None, "completed": completed}
        save_checkpoint(checkpoint_file, payload)
        print(f"{kind}: updated {chunk_updated} item(s)")
        if max_items is not None and updated >= max_items:
            remaining_tables = [item for item in selected if item not in completed]
            if remaining_tables:
                payload = {
                    "table": remaining_tables[0],
                    "exclusiveStartKey": None,
                    "completed": completed,
                }
                save_checkpoint(checkpoint_file, payload)
                return updated, payload
            break

    if set(completed) >= set(selected):
        save_checkpoint(checkpoint_file, None)
        return updated, None
    payload = {
        "table": next(name for name in selected if name not in completed),
        "exclusiveStartKey": None,
        "completed": completed,
    }
    save_checkpoint(checkpoint_file, payload)
    return updated, payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill timelineKey on status, audit, and staff-comment rows."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--table", choices=tuple(TABLES), default=None)
    parser.add_argument(
        "--exclusive-start-key",
        default=None,
        help="Resume one table from a prior LastEvaluatedKey JSON object.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Soft stop after at least this many updates; the current page is finished first.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Stop after this many scan pages in the current invocation.",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="Stop after this many seconds in the current invocation.",
    )
    parser.add_argument(
        "--checkpoint-file",
        default=None,
        help="Persist the latest resume checkpoint after every chunk.",
    )
    args = parser.parse_args()
    start_key = None
    if args.exclusive_start_key:
        start_key = json.loads(args.exclusive_start_key)
        if not isinstance(start_key, dict):
            raise SystemExit("--exclusive-start-key must be a JSON object")
    checkpoint_path = Path(args.checkpoint_file) if args.checkpoint_file else None
    count, resume = backfill(
        dry_run=args.dry_run,
        table_name=args.table,
        exclusive_start_key=start_key,
        max_items=args.max_items,
        max_pages=args.max_pages,
        max_seconds=args.max_seconds,
        checkpoint_file=checkpoint_path,
    )
    print(f"Done. Updated {count} item(s).")
    if resume:
        print("Resume with:")
        command = "  python scripts/db/backfill_activity_timeline_keys.py"
        if checkpoint_path is not None:
            command += f" --checkpoint-file '{checkpoint_path}'"
        else:
            if resume.get("table"):
                command += f" --table {resume['table']}"
            if resume.get("exclusiveStartKey"):
                command += (
                    " --exclusive-start-key "
                    f"'{json.dumps(resume['exclusiveStartKey'], separators=(',', ':'))}'"
                )
        print(command)


if __name__ == "__main__":
    main()
