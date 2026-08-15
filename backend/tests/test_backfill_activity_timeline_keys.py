"""Resumable activity-timeline key backfill and cutover visibility."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import Settings
from app.database.activity_timeline import build_timeline_key
from app.database.dynamo_audit_history_store import DynamoAuditHistoryStore
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.schemas.stored_audit_history import StoredAuditHistory
from scripts.db import backfill_activity_timeline_keys as backfill_mod


class PagedFakeTable:
    def __init__(self, pages: list[list[dict[str, Any]]]) -> None:
        self.pages = pages
        self.updates: list[dict[str, Any]] = []

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        start = kwargs.get("ExclusiveStartKey")
        index = 0
        if isinstance(start, dict) and "page" in start:
            index = int(start["page"])
        items = list(self.pages[index]) if index < len(self.pages) else []
        last_key = {"page": index + 1} if index + 1 < len(self.pages) else None
        return {"Items": items, "LastEvaluatedKey": last_key}

    def update_item(self, **kwargs: Any) -> dict[str, Any]:
        self.updates.append(kwargs)
        return {}


def _legacy_item(item_id: str, *, created_at: str, with_key: bool = False) -> dict[str, Any]:
    item = {
        "auditId": item_id,
        "ticketId": "tkt_legacy",
        "actionType": "WORK_ORDER_START",
        "summary": "Work order started.",
        "createdAt": created_at,
    }
    if with_key:
        item["timelineKey"] = build_timeline_key("audit", item_id, created_at)
    return item


def test_max_pages_emits_checkpoint_and_resume_finishes(tmp_path: Path) -> None:
    page1 = [
        _legacy_item("audit_a", created_at="2026-01-01T00:00:01Z"),
        _legacy_item("audit_b", created_at="2026-01-01T00:00:02Z"),
    ]
    page2 = [_legacy_item("audit_c", created_at="2026-01-01T00:00:03Z")]
    first = PagedFakeTable([page1, page2])
    checkpoint = tmp_path / "timeline.checkpoint.json"

    updated, resume = backfill_mod.backfill(
        table_name="audit",
        max_pages=1,
        checkpoint_file=checkpoint,
        tables={"audit": first, "status": PagedFakeTable([]), "comments": PagedFakeTable([])},
    )

    assert updated == 2
    assert resume == {
        "table": "audit",
        "exclusiveStartKey": {"page": 1},
        "completed": [],
    }
    assert json_checkpoint(checkpoint) == resume
    assert {call["Key"]["auditId"] for call in first.updates} == {"audit_a", "audit_b"}

    page1_done = [
        _legacy_item("audit_a", created_at="2026-01-01T00:00:01Z", with_key=True),
        _legacy_item("audit_b", created_at="2026-01-01T00:00:02Z", with_key=True),
    ]
    second = PagedFakeTable([page1_done, page2])
    updated2, resume2 = backfill_mod.backfill(
        table_name="audit",
        checkpoint_file=checkpoint,
        tables={"audit": second, "status": PagedFakeTable([]), "comments": PagedFakeTable([])},
    )
    assert updated2 == 1
    assert resume2 is None
    assert not checkpoint.exists()
    assert {call["Key"]["auditId"] for call in second.updates} == {"audit_c"}


def test_max_items_finishes_current_page_before_checkpoint(tmp_path: Path) -> None:
    page1 = [
        _legacy_item("audit_a", created_at="2026-01-01T00:00:01Z"),
        _legacy_item("audit_b", created_at="2026-01-01T00:00:02Z"),
    ]
    page2 = [_legacy_item("audit_c", created_at="2026-01-01T00:00:03Z")]
    table = PagedFakeTable([page1, page2])
    checkpoint = tmp_path / "timeline.checkpoint.json"

    updated, resume = backfill_mod.backfill(
        table_name="audit",
        max_items=1,
        checkpoint_file=checkpoint,
        tables={"audit": table, "status": PagedFakeTable([]), "comments": PagedFakeTable([])},
    )
    assert updated == 2
    assert resume["exclusiveStartKey"] == {"page": 1}
    assert {call["Key"]["auditId"] for call in table.updates} == {"audit_a", "audit_b"}


def test_multi_table_resume_advances_completed_tables(tmp_path: Path) -> None:
    status = PagedFakeTable(
        [[{"historyId": "h1", "createdAt": "2026-01-01T00:00:01Z", "ticketId": "tkt"}]]
    )
    audit = PagedFakeTable(
        [[{"auditId": "a1", "createdAt": "2026-01-01T00:00:02Z", "ticketId": "tkt"}]]
    )
    comments = PagedFakeTable(
        [[{"commentId": "c1", "createdAt": "2026-01-01T00:00:03Z", "ticketId": "tkt"}]]
    )
    checkpoint = tmp_path / "timeline.checkpoint.json"

    updated, resume = backfill_mod.backfill(
        max_items=1,
        checkpoint_file=checkpoint,
        tables={"status": status, "audit": audit, "comments": comments},
    )
    assert updated == 1
    assert resume["completed"] == ["status"]
    assert resume["table"] == "audit"

    updated2, resume2 = backfill_mod.backfill(
        checkpoint_file=checkpoint,
        tables={"status": status, "audit": audit, "comments": comments},
    )
    assert updated2 == 2
    assert resume2 is None
    assert not checkpoint.exists()
    assert status.updates and audit.updates and comments.updates


def json_checkpoint(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _put_legacy_audit(settings: Settings, *, audit_id: str, created_at: str) -> None:
    table = create_dynamodb_resource(settings).Table(
        build_table_name(settings.dynamodb_table_prefix, "ticket-audit-history")
    )
    table.put_item(
        Item={
            "auditId": audit_id,
            "ticketId": "tkt_cutover",
            "actionType": "WORK_ORDER_START",
            "summary": "Work order wo_hidden started.",
            "createdAt": created_at,
        }
    )


def test_legacy_row_stays_visible_before_and_during_gsi_cutover(
    dynamodb_settings: Settings,
) -> None:
    _put_legacy_audit(dynamodb_settings, audit_id="audit_legacy", created_at="2026-01-01T00:00:01Z")
    dynamodb_settings.activity_timeline_use_gsi = True
    keyed_store = DynamoAuditHistoryStore(dynamodb_settings)
    keyed_store.append(
        StoredAuditHistory(
            auditId="audit_new",
            ticketId="tkt_cutover",
            actionType="WORK_ORDER_COMPLETE",
            summary="Work order completed.",
            createdAt="2026-01-01T00:00:02Z",
        )
    )

    gsi_page, _next = keyed_store.list_by_ticket_id_page("tkt_cutover", limit=10)
    assert [item.audit_id for item in gsi_page] == ["audit_legacy", "audit_new"]

    dynamodb_settings.activity_timeline_use_gsi = False
    compat_store = DynamoAuditHistoryStore(dynamodb_settings)
    compat_page, _next = compat_store.list_by_ticket_id_page("tkt_cutover", limit=10)
    assert [item.audit_id for item in compat_page] == ["audit_legacy", "audit_new"]


def test_backfill_then_gsi_read_includes_migrated_legacy_row(
    dynamodb_settings: Settings, tmp_path: Path
) -> None:
    _put_legacy_audit(dynamodb_settings, audit_id="audit_legacy", created_at="2026-01-01T00:00:01Z")
    checkpoint = tmp_path / "timeline.checkpoint.json"
    updated, resume = backfill_mod.backfill(
        table_name="audit",
        max_pages=1,
        checkpoint_file=checkpoint,
    )
    assert updated >= 1
    if resume:
        updated2, resume2 = backfill_mod.backfill(
            table_name="audit",
            checkpoint_file=checkpoint,
        )
        assert resume2 is None
        assert updated2 >= 0

    table = create_dynamodb_resource(dynamodb_settings).Table(
        build_table_name(dynamodb_settings.dynamodb_table_prefix, "ticket-audit-history")
    )
    item = table.get_item(Key={"auditId": "audit_legacy"})["Item"]
    assert item["timelineKey"] == build_timeline_key(
        "audit", "audit_legacy", "2026-01-01T00:00:01Z"
    )

    dynamodb_settings.activity_timeline_use_gsi = True
    store = DynamoAuditHistoryStore(dynamodb_settings)
    page, next_key = store.list_by_ticket_id_page("tkt_cutover", limit=10)
    assert [item.audit_id for item in page] == ["audit_legacy"]
    assert next_key is None
