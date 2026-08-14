"""Staff GSI key backfill resume behavior (issue #267)."""

from __future__ import annotations

from typing import Any

from scripts.db import backfill_staff_ticket_keys as backfill_mod


def _ticket_item(ticket_id: str, *, with_keys: bool = False) -> dict[str, Any]:
    item: dict[str, Any] = {
        "ticketId": ticket_id,
        "ticketNumber": f"BG-2026-{ticket_id[-4:]}",
        "trackingCode": "AAAAAA",
        "description": "Staff key backfill fixture.",
        "contact": {"name": "Test", "phone": "+96170123456"},
        "location": {
            "latitude": 33.89,
            "longitude": 35.48,
            "addressText": "Beirut",
            "source": "GPS",
        },
        "imageObjectKey": "reports/raw.jpg",
        "status": "SUBMITTED",
        "category": "road_damage",
        "createdAt": "2026-08-01T00:00:00Z",
        "municipalityId": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    }
    if with_keys:
        item["staffScopeKey"] = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        item["staffSortKey"] = f"2026-08-01T00:00:00Z#{ticket_id}"
        item["adminBrowseKey"] = "ALL"
    return item


class PagedFakeTable:
    """Scan returns fixed pages; ExclusiveStartKey selects the next page."""

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


def test_max_items_finishes_scan_page_before_resume_checkpoint():
    """A soft --max-items stop must not skip remaining items on the current page."""
    page1 = [
        _ticket_item("tkt_page1_a"),
        _ticket_item("tkt_page1_b"),
        _ticket_item("tkt_page1_c"),
    ]
    page2 = [
        _ticket_item("tkt_page2_a"),
        _ticket_item("tkt_page2_b"),
    ]
    table = PagedFakeTable([page1, page2])

    updated, resume_key = backfill_mod.backfill(
        dry_run=False,
        max_items=1,
        table=table,
    )

    # Soft stop at 1 still finishes page 1 (3 updates), then checkpoints.
    assert updated == 3
    assert resume_key == {"page": 1}
    assert len(table.updates) == 3
    updated_ids = {call["Key"]["ticketId"] for call in table.updates}
    assert updated_ids == {"tkt_page1_a", "tkt_page1_b", "tkt_page1_c"}

    # Mark page-1 rows as already backfilled so a resume run only touches page 2.
    page1_done = [
        _ticket_item("tkt_page1_a", with_keys=True),
        _ticket_item("tkt_page1_b", with_keys=True),
        _ticket_item("tkt_page1_c", with_keys=True),
    ]
    resume_table = PagedFakeTable([page1_done, page2])
    updated2, resume_key2 = backfill_mod.backfill(
        dry_run=False,
        exclusive_start_key=resume_key,
        table=resume_table,
    )

    assert updated2 == 2
    assert resume_key2 is None
    assert {call["Key"]["ticketId"] for call in resume_table.updates} == {
        "tkt_page2_a",
        "tkt_page2_b",
    }


def test_dry_run_max_items_also_finishes_current_page():
    page1 = [_ticket_item("tkt_dry_a"), _ticket_item("tkt_dry_b")]
    page2 = [_ticket_item("tkt_dry_c")]
    table = PagedFakeTable([page1, page2])

    updated, resume_key = backfill_mod.backfill(
        dry_run=True,
        max_items=1,
        table=table,
    )

    assert updated == 2
    assert resume_key == {"page": 1}
    assert table.updates == []
