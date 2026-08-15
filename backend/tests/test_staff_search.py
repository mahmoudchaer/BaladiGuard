"""Staff global search authorization, field safety, and bounds (issue #42 / #260)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.database.memory import ticket_store
from app.services.staff.search import MAX_SEARCH_QUERY_LENGTH, MIN_SEARCH_QUERY_LENGTH
from tests.conftest import contribution_ready_auth_headers, issue_test_staff_token
from tests.test_staff_assistant import _ticket
from tests.test_submit_ticket import VALID_PAYLOAD
from tests.test_workforce import BEIRUT, OTHER_MUNICIPALITY, ROAD, WASTE

ROADS = ROAD


def _headers(client: TestClient, username: str = "admin") -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username=username)}"}


def _search(client: TestClient, query: str, *, username: str = "admin"):
    return client.get("/v1/staff-search", params={"q": query}, headers=_headers(client, username))


def test_staff_search_requires_authentication(anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/v1/staff-search", params={"q": "BG"}).status_code == 401


def test_staff_search_rejects_short_and_long_queries(anonymous_client: TestClient) -> None:
    short = _search(anonymous_client, "x")
    assert short.status_code == 400
    assert short.json()["error"]["code"] == "VALIDATION_ERROR"
    long_query = "a" * (MAX_SEARCH_QUERY_LENGTH + 1)
    long_response = anonymous_client.get(
        "/v1/staff-search",
        params={"q": long_query},
        headers=_headers(anonymous_client),
    )
    assert long_response.status_code in {400, 422}
    assert MIN_SEARCH_QUERY_LENGTH == 2


def test_staff_search_finds_normalized_ticket_and_tracking_references(
    anonymous_client: TestClient,
) -> None:
    ticket_id = _ticket(
        anonymous_client,
        area="Hamra",
        priority="high",
        department=ROADS,
        public_location_label="Hamra gate",
    )
    stored = ticket_store.get(ticket_id)
    assert stored is not None

    by_id = _search(anonymous_client, stored.ticket_id)
    assert by_id.status_code == 200
    assert [item["ticketId"] for item in by_id.json()["tickets"]] == [ticket_id]

    by_number = _search(anonymous_client, stored.ticket_number.lower())
    assert [item["ticketId"] for item in by_number.json()["tickets"]] == [ticket_id]

    spaced = f"{stored.tracking_code[:3]} {stored.tracking_code[3:]}"
    by_tracking = _search(anonymous_client, spaced)
    assert [item["ticketId"] for item in by_tracking.json()["tickets"]] == [ticket_id]
    assert by_tracking.json()["tickets"][0]["trackingCode"] == stored.tracking_code


def test_staff_search_matches_safe_address_not_private_fields(
    anonymous_client: TestClient,
) -> None:
    ticket_id = _ticket(
        anonymous_client,
        area="Secret alley 99",
        priority="high",
        department=ROADS,
        description="Call +96170111999 and ask for Nour Private",
        public_location_label="University gate",
    )
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    ticket_store.save(
        stored.model_copy(
            update={
                "contact": stored.contact.model_copy(
                    update={"phone": "+96170111999", "email": "nour@example.com", "name": "Nour"}
                )
            }
        )
    )

    assert (
        _search(anonymous_client, "University gate").json()["tickets"][0]["ticketId"] == ticket_id
    )
    assert _search(anonymous_client, "+96170111999").json()["tickets"] == []
    assert _search(anonymous_client, "nour@example.com").json()["tickets"] == []
    assert _search(anonymous_client, "Nour Private").json()["tickets"] == []
    assert _search(anonymous_client, "Secret alley 99").json()["tickets"] == []
    hit = _search(anonymous_client, "University gate").json()["tickets"][0]
    assert "contact" not in hit
    assert "description" not in hit
    assert "imageObjectKey" not in hit
    assert hit["publicLocationLabel"] == "University gate"


def test_staff_search_hides_inaccessible_municipality_and_department_records(
    anonymous_client: TestClient,
) -> None:
    visible = _ticket(
        anonymous_client,
        area="Hamra",
        priority="high",
        department=ROADS,
        public_location_label="Shared label",
    )
    _ticket(
        anonymous_client,
        area="Tripoli",
        priority="high",
        department=ROADS,
        municipality=OTHER_MUNICIPALITY,
        public_location_label="Shared label",
    )
    _ticket(
        anonymous_client,
        area="Waste",
        priority="high",
        department=WASTE,
        public_location_label="Shared label",
    )

    staff_hits = _search(anonymous_client, "Shared label", username="staff")
    assert staff_hits.status_code == 200
    assert [item["ticketId"] for item in staff_hits.json()["tickets"]] == [visible]


def test_staff_search_groups_workers_teams_and_work_orders(
    anonymous_client: TestClient,
) -> None:
    created = anonymous_client.post(
        "/v1/tickets", json=VALID_PAYLOAD, headers=contribution_ready_auth_headers()
    )
    assert created.status_code == 201
    ticket_id = created.json()["ticketId"]
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    ticket_store.save(
        stored.model_copy(
            update={
                "municipality_id": BEIRUT,
                "department_id": ROADS,
                "status": "IN_PROGRESS",
                "public_location_label": "Corniche",
            }
        )
    )

    worker = anonymous_client.post(
        "/v1/workforce/workers",
        json={
            "municipalityId": BEIRUT,
            "displayName": "Searchable Crew",
            "departmentIds": [ROADS],
        },
        headers=_headers(anonymous_client),
    )
    assert worker.status_code == 201, worker.text
    team = anonymous_client.post(
        "/v1/workforce/teams",
        json={
            "municipalityId": BEIRUT,
            "displayName": "Searchable Team",
            "departmentIds": [ROADS],
            "workerIds": [worker.json()["workerId"]],
        },
        headers=_headers(anonymous_client),
    )
    assert team.status_code == 201, team.text
    work_order = anonymous_client.post(
        f"/v1/tickets/{ticket_id}/work-orders",
        json={"summary": "Inspect searchable culvert"},
        headers=_headers(anonymous_client),
    )
    assert work_order.status_code == 201, work_order.text

    body = _search(anonymous_client, "Searchable").json()
    assert [item["workerId"] for item in body["workers"]] == [worker.json()["workerId"]]
    assert [item["teamId"] for item in body["teams"]] == [team.json()["teamId"]]
    assert [item["workOrderId"] for item in body["workOrders"]] == [
        work_order.json()["workOrderId"]
    ]
    assert body["workOrders"][0]["ticketId"] == ticket_id
    assert "completionNote" not in body["workOrders"][0]
    assert body["limits"]["ticketScanBudget"] == 200
    assert body["limits"]["maxResultsPerType"] == 8


def test_staff_search_work_order_id_requires_ticket_access(
    anonymous_client: TestClient,
) -> None:
    created = anonymous_client.post(
        "/v1/tickets", json=VALID_PAYLOAD, headers=contribution_ready_auth_headers()
    )
    ticket_id = created.json()["ticketId"]
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    ticket_store.save(
        stored.model_copy(
            update={
                "municipality_id": OTHER_MUNICIPALITY,
                "department_id": ROADS,
                "status": "IN_PROGRESS",
            }
        )
    )
    work_order = anonymous_client.post(
        f"/v1/tickets/{ticket_id}/work-orders",
        json={"summary": "Hidden culvert"},
        headers=_headers(anonymous_client),
    )
    assert work_order.status_code == 201
    hidden = _search(anonymous_client, work_order.json()["workOrderId"], username="staff")
    assert hidden.json()["workOrders"] == []


def test_ticket_ids_filter_returns_accessible_ids_only(anonymous_client: TestClient) -> None:
    visible = _ticket(anonymous_client, area="Hamra", priority="high", department=ROADS)
    hidden = _ticket(
        anonymous_client,
        area="Tripoli",
        priority="high",
        department=ROADS,
        municipality=OTHER_MUNICIPALITY,
    )
    response = anonymous_client.get(
        "/v1/tickets",
        params={"ticketIds": f"{visible},{hidden},tkt_missing", "openOnly": "true"},
        headers=_headers(anonymous_client, "staff"),
    )
    assert response.status_code == 200
    assert [item["ticketId"] for item in response.json()["items"]] == [visible]


def test_ticket_ids_filter_rejects_too_many_ids(anonymous_client: TestClient) -> None:
    ids = ",".join(f"tkt_{index:02d}" for index in range(21))
    response = anonymous_client.get(
        "/v1/tickets",
        params={"ticketIds": ids},
        headers=_headers(anonymous_client),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
