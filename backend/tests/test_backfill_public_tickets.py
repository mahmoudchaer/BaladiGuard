"""Safe public-ticket backfill behavior."""

from __future__ import annotations

from typing import Any

from scripts.db import backfill_public_tickets as backfill_mod


class FakeTable:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self.updates: list[dict[str, Any]] = []

    def scan(self, **kwargs):
        return {"Items": list(self.items)}

    def update_item(self, **kwargs):
        self.updates.append(kwargs)


def test_backfill_does_not_publish_draft_or_copy_raw_fields(monkeypatch):
    items = [
        {
            "ticketId": "tkt_draft",
            "ticketNumber": "BG-2026-0001",
            "trackingCode": "AAAAAA",
            "description": "Raw citizen text with house number 12",
            "location": {
                "latitude": 33.89,
                "longitude": 35.48,
                "addressText": "12 Exact Street, Beirut",
                "source": "GPS",
            },
            "imageObjectKey": "reports/raw.jpg",
            "status": "SUBMITTED",
            "category": "road_damage",
            "finalCategory": "road_damage",
            "publicStatus": "DRAFT",
            "contact": {"phone": "+96170123456"},
            "createdAt": "2026-08-01T00:00:00Z",
        },
        {
            "ticketId": "tkt_published_missing_sort",
            "ticketNumber": "BG-2026-0002",
            "trackingCode": "BBBBBB",
            "description": "Raw should stay unused",
            "location": {
                "latitude": 33.89,
                "longitude": 35.48,
                "addressText": "Exact private address",
                "source": "GPS",
            },
            "imageObjectKey": "reports/raw2.jpg",
            "status": "SUBMITTED",
            "category": "road_damage",
            "finalCategory": "road_damage",
            "publicStatus": "PUBLISHED",
            "publicDescription": "Staff-approved summary",
            "publicLocationLabel": "Hamra, Beirut",
            "publicPublishedAt": "2026-08-02T00:00:00Z",
            "contact": {"phone": "+96170123456"},
            "createdAt": "2026-08-01T00:00:00Z",
            "updatedAt": "2026-08-02T00:00:00Z",
        },
    ]
    table = FakeTable(items)

    class FakeResource:
        def Table(self, _name):
            return table

    monkeypatch.setattr(
        backfill_mod, "get_settings", lambda: type("S", (), {"dynamodb_table_prefix": "bg"})()
    )
    monkeypatch.setattr(backfill_mod, "create_dynamodb_resource", lambda _settings: FakeResource())
    monkeypatch.setattr(backfill_mod, "build_table_name", lambda prefix, name: f"{prefix}-{name}")

    updated = backfill_mod.backfill(dry_run=False)

    assert updated == 1
    assert len(table.updates) == 1
    values = table.updates[0]["ExpressionAttributeValues"]
    assert ":publicSortKey" in values
    assert values[":publicPublishedAt"] == "2026-08-02T00:00:00Z"
    # Ensure we never wrote raw citizen description/address as public fields.
    expr = table.updates[0]["UpdateExpression"]
    assert "publicDescription" not in expr
    assert "publicLocationLabel" not in expr
    assert "publicStatus" not in expr
