"""Staff ticket collection, map viewport, and aggregates (issue #267)."""

from __future__ import annotations

from app.database.memory import ticket_store
from app.services.ai_job_queue import ai_job_queue
from tests.conftest import contribution_ready_auth_headers, issue_test_staff_token
from tests.test_submit_ticket import VALID_PAYLOAD

BEIRUT_MUNICIPALITY = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
OTHER_MUNICIPALITY = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ROAD_MAINTENANCE = "d1111111-1111-1111-1111-111111111111"
WASTE_MANAGEMENT = "d2222222-2222-2222-2222-222222222222"


def _create_ticket(client, description: str = VALID_PAYLOAD["description"]) -> dict:
    response = client.post(
        "/v1/tickets",
        json={**VALID_PAYLOAD, "description": description},
        headers=contribution_ready_auth_headers(),
    )
    assert response.status_code == 201, response.text
    assert ai_job_queue.run_once().outcome == "succeeded"
    return response.json()


def _staff_headers(client, username: str = "admin") -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username=username)}"}


def _stamp_scope(
    ticket_id: str,
    *,
    municipality_id: str | None = BEIRUT_MUNICIPALITY,
    department_id: str | None = ROAD_MAINTENANCE,
) -> None:
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    ticket_store.save(
        stored.model_copy(
            update={
                "municipality_id": municipality_id,
                "department_id": department_id,
            }
        )
    )


def test_paginated_list_is_lightweight(client):
    created = _create_ticket(client)

    response = client.get("/v1/tickets", params={"limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert body["limit"] == 10
    assert body["freshnessHintSeconds"] == 30
    item = next(ticket for ticket in body["items"] if ticket["ticketId"] == created["ticketId"])
    assert "trackingCode" not in item
    assert "contact" not in item
    assert "statusHistory" not in item
    assert "auditHistory" not in item
    assert "imageReferences" not in item
    assert "imageObjectKey" not in item
    assert "ai" not in item
    assert "public" not in item
    assert "duplicateSuggestions" not in item
    assert set(item["location"]) == {"latitude", "longitude", "addressText"}
    assert item["assignmentState"] in {"assigned", "unassigned"}
    assert isinstance(item["summary"], str)


def test_cursor_pagination_is_stable_and_complete(client):
    created_ids = [
        _create_ticket(client, f"Pagination ticket number {index} for stability.")["ticketId"]
        for index in range(5)
    ]

    first = client.get("/v1/tickets", params={"limit": 2})
    assert first.status_code == 200
    page1 = first.json()
    assert len(page1["items"]) == 2
    assert page1["nextCursor"]

    second = client.get(
        "/v1/tickets",
        params={"limit": 2, "cursor": page1["nextCursor"]},
    )
    assert second.status_code == 200
    page2 = second.json()
    assert len(page2["items"]) == 2
    assert page2["nextCursor"]

    third = client.get(
        "/v1/tickets",
        params={"limit": 2, "cursor": page2["nextCursor"]},
    )
    assert third.status_code == 200
    page3 = third.json()
    assert len(page3["items"]) >= 1

    ids1 = {item["ticketId"] for item in page1["items"]}
    ids2 = {item["ticketId"] for item in page2["items"]}
    ids3 = {item["ticketId"] for item in page3["items"]}
    assert not ids1.intersection(ids2)
    assert not ids1.intersection(ids3)
    assert not ids2.intersection(ids3)
    assert set(created_ids).issubset(ids1 | ids2 | ids3)


def test_cursor_pagination_supports_page_back_navigation(client):
    """Page 1 → page 2 → page 1 keeps stable ordering (client history + forward cursors)."""
    created_ids = [
        _create_ticket(client, f"Back-nav ticket {index} for previous page.")["ticketId"]
        for index in range(4)
    ]

    first = client.get("/v1/tickets", params={"limit": 2})
    assert first.status_code == 200
    page1 = first.json()
    assert len(page1["items"]) == 2
    assert page1["nextCursor"]
    assert page1["previousCursor"] is None
    page1_ids = [item["ticketId"] for item in page1["items"]]

    second = client.get(
        "/v1/tickets",
        params={"limit": 2, "cursor": page1["nextCursor"]},
    )
    assert second.status_code == 200
    page2 = second.json()
    assert len(page2["items"]) == 2
    page2_ids = [item["ticketId"] for item in page2["items"]]
    assert page1_ids != page2_ids

    # Returning to the first page (null cursor) restores the original ordering.
    back = client.get("/v1/tickets", params={"limit": 2})
    assert back.status_code == 200
    assert [item["ticketId"] for item in back.json()["items"]] == page1_ids
    assert set(created_ids).issuperset(set(page1_ids) | set(page2_ids))


def _staff_next_cursor_from_query_state(
    *,
    last_key: dict | None,
    items: list,
    limit: int,
) -> bool:
    """Mirror Dynamo list_staff_page continuation rules for unit coverage."""
    if last_key:
        return True
    return len(items) == limit and bool(items)


def test_sparse_filter_continuation_keeps_next_cursor_when_page_not_full():
    # Bounded rounds can stop with items < limit while LastEvaluatedKey remains.
    assert (
        _staff_next_cursor_from_query_state(
            last_key={"ticketId": "tkt_more", "staffSortKey": "x"},
            items=["only-one"],
            limit=25,
        )
        is True
    )
    assert (
        _staff_next_cursor_from_query_state(
            last_key=None,
            items=["a", "b"],
            limit=25,
        )
        is False
    )
    assert (
        _staff_next_cursor_from_query_state(
            last_key=None,
            items=list(range(25)),
            limit=25,
        )
        is True
    )


def test_assignment_state_and_search_filters_are_server_side(client):
    assigned = _create_ticket(client, "Assigned search needle ALPHA unique phrase.")
    unassigned = _create_ticket(client, "Unassigned search needle BETA unique phrase.")
    _stamp_scope(assigned["ticketId"], department_id=ROAD_MAINTENANCE)
    _stamp_scope(unassigned["ticketId"], department_id=None)

    unassigned_page = client.get("/v1/tickets", params={"assignmentState": "unassigned"})
    assert unassigned_page.status_code == 200
    unassigned_ids = {item["ticketId"] for item in unassigned_page.json()["items"]}
    assert unassigned["ticketId"] in unassigned_ids
    assert assigned["ticketId"] not in unassigned_ids

    search_page = client.get("/v1/tickets", params={"q": "ALPHA unique"})
    assert search_page.status_code == 200
    search_ids = {item["ticketId"] for item in search_page.json()["items"]}
    assert assigned["ticketId"] in search_ids
    assert unassigned["ticketId"] not in search_ids


def test_municipal_staff_list_is_scoped(anonymous_client, client):
    visible = _create_ticket(client, "Visible road ticket in Beirut.")
    unassigned = _create_ticket(client, "Unassigned but same municipality.")
    other_dept = _create_ticket(client, "Waste ticket outside staff departments.")
    other_muni = _create_ticket(client, "Road ticket in another municipality.")
    _stamp_scope(visible["ticketId"], department_id=ROAD_MAINTENANCE)
    _stamp_scope(unassigned["ticketId"], department_id=None)
    _stamp_scope(other_dept["ticketId"], department_id=WASTE_MANAGEMENT)
    _stamp_scope(
        other_muni["ticketId"],
        municipality_id=OTHER_MUNICIPALITY,
        department_id=ROAD_MAINTENANCE,
    )

    response = anonymous_client.get(
        "/v1/tickets",
        headers=_staff_headers(anonymous_client, "staff"),
    )

    assert response.status_code == 200
    visible_ids = {item["ticketId"] for item in response.json()["items"]}
    assert visible["ticketId"] in visible_ids
    assert unassigned["ticketId"] in visible_ids
    assert other_dept["ticketId"] not in visible_ids
    assert other_muni["ticketId"] not in visible_ids


def test_map_viewport_returns_clusters_or_markers(client):
    created = _create_ticket(client)
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    lat = stored.location.latitude
    lng = stored.location.longitude

    clustered = client.get(
        "/v1/tickets/map",
        params={
            "north": lat + 0.2,
            "south": lat - 0.2,
            "east": lng + 0.2,
            "west": lng - 0.2,
            "zoom": 10,
            "limit": 200,
        },
    )
    assert clustered.status_code == 200
    cluster_body = clustered.json()
    assert cluster_body["zoom"] == 10
    assert cluster_body["markers"] == []
    assert len(cluster_body["clusters"]) >= 1
    assert cluster_body["clusters"][0]["count"] >= 1

    markers = client.get(
        "/v1/tickets/map",
        params={
            "north": lat + 0.2,
            "south": lat - 0.2,
            "east": lng + 0.2,
            "west": lng - 0.2,
            "zoom": 15,
            "limit": 200,
        },
    )
    assert markers.status_code == 200
    marker_body = markers.json()
    assert marker_body["clusters"] == []
    assert any(item["ticketId"] == created["ticketId"] for item in marker_body["markers"])
    marker = next(
        item for item in marker_body["markers"] if item["ticketId"] == created["ticketId"]
    )
    assert set(marker) >= {
        "ticketId",
        "ticketNumber",
        "status",
        "priority",
        "latitude",
        "longitude",
        "category",
    }
    assert "trackingCode" not in marker
    assert "contact" not in marker


def test_aggregates_requires_staff_auth_and_shape(client):
    _create_ticket(client)

    from fastapi.testclient import TestClient

    from app.main import app

    denied = TestClient(app).get("/v1/tickets/aggregates")
    assert denied.status_code == 401

    response = client.get("/v1/tickets/aggregates")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "openCount",
        "criticalCount",
        "highCount",
        "unassignedCount",
        "overdueCount",
        "approximate",
    }
    assert body["approximate"] is False
    assert body["openCount"] >= 1


def test_overdue_filter_continues_past_non_matching_source_page(client):
    """Aging/overdue must not return empty when newer on-track tickets fill the raw page."""
    from datetime import UTC, datetime, timedelta

    marker = "SLA-CONTINUATION-MARKER-267"
    now = datetime.now(UTC)

    on_track_ids: list[str] = []
    for index in range(3):
        created = _create_ticket(
            client,
            f"{marker} on-track filler ticket number {index} for overdue continue.",
        )
        stored = ticket_store.get(created["ticketId"])
        assert stored is not None
        # High ack window is 24h; created 1h ago stays on_track.
        created_at = (now - timedelta(hours=1, minutes=index)).isoformat().replace("+00:00", "Z")
        ticket_store.save(
            stored.model_copy(
                update={
                    "priority": "high",
                    "status": "SUBMITTED",
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            )
        )
        on_track_ids.append(created["ticketId"])

    overdue = _create_ticket(
        client,
        f"{marker} overdue ticket that must surface after on-track pages.",
    )
    stored = ticket_store.get(overdue["ticketId"])
    assert stored is not None
    overdue_created = (now - timedelta(hours=48)).isoformat().replace("+00:00", "Z")
    ticket_store.save(
        stored.model_copy(
            update={
                "priority": "high",
                "status": "SUBMITTED",
                "created_at": overdue_created,
                "updated_at": overdue_created,
            }
        )
    )

    response = client.get(
        "/v1/tickets",
        params={"limit": 2, "slaState": "overdue", "q": marker},
    )
    assert response.status_code == 200
    body = response.json()
    ids = {item["ticketId"] for item in body["items"]}
    assert overdue["ticketId"] in ids
    assert not ids.intersection(on_track_ids)
