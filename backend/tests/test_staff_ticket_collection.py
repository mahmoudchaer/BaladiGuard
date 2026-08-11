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
