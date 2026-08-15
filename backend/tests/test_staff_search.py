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
    assert body["limits"]["workforceScanBudget"] == 80
    assert body["limits"]["workOrderQueryBudget"] == 40
    assert body["workforceScanTruncated"] is False
    assert body["workOrderScanTruncated"] is False


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


def test_staff_search_bounds_large_workforce_directory(
    anonymous_client: TestClient, monkeypatch
) -> None:
    from app.database.memory_workforce import workforce_store
    from app.schemas.workforce import StoredWorker
    from app.services.staff import search as search_mod

    now = "2026-08-15T12:00:00Z"
    for index in range(120):
        workforce_store.save_worker(
            StoredWorker(
                workerId=f"wrk_{index:04d}",
                municipalityId=BEIRUT,
                displayName=f"Crew {index:04d}",
                departmentIds=[ROADS],
                teamIds=[],
                active=True,
                createdAt=now,
                updatedAt=now,
            )
        )
    workforce_store.save_worker(
        StoredWorker(
            workerId="wrk_zebra_unique",
            municipalityId=BEIRUT,
            displayName="Zebra Unique",
            departmentIds=[ROADS],
            teamIds=[],
            active=True,
            createdAt=now,
            updatedAt=now,
        )
    )

    list_calls = {"workers": 0, "teams": 0}
    original_workers = workforce_store.list_workers
    original_teams = workforce_store.list_teams

    def counted_workers(*args, **kwargs):
        list_calls["workers"] += 1
        return original_workers(*args, **kwargs)

    def counted_teams(*args, **kwargs):
        list_calls["teams"] += 1
        return original_teams(*args, **kwargs)

    monkeypatch.setattr(workforce_store, "list_workers", counted_workers)
    monkeypatch.setattr(workforce_store, "list_teams", counted_teams)
    monkeypatch.setattr(search_mod, "WORKFORCE_SCAN_BUDGET", 80)

    crew = _search(anonymous_client, "Crew").json()
    assert list_calls["workers"] == 0
    assert list_calls["teams"] == 0
    assert len(crew["workers"]) == 8
    assert crew["workersTruncated"] is True
    assert crew["workforceScanTruncated"] is True
    assert crew["limits"]["workforceScanBudget"] == 80

    exact = _search(anonymous_client, "wrk_zebra_unique").json()
    assert [item["workerId"] for item in exact["workers"]] == ["wrk_zebra_unique"]
    assert exact["workforceScanTruncated"] is False
    assert list_calls["workers"] == 0


def test_staff_search_bounds_work_order_ticket_queries(
    anonymous_client: TestClient, monkeypatch
) -> None:
    from app.database.memory_work_order import work_order_store
    from app.services.staff import search as search_mod

    monkeypatch.setattr(search_mod, "WORK_ORDER_QUERY_BUDGET", 3)
    created_ids: list[str] = []
    for index in range(6):
        ticket_id = _ticket(
            anonymous_client,
            area=f"Area {index}",
            priority="high",
            department=ROADS,
            public_location_label=f"Label {index}",
            status="IN_PROGRESS",
        )
        created_ids.append(ticket_id)
        work_order = anonymous_client.post(
            f"/v1/tickets/{ticket_id}/work-orders",
            json={"summary": f"Inspect culvert {index}"},
            headers=_headers(anonymous_client),
        )
        assert work_order.status_code == 201, work_order.text

    original = work_order_store.list_by_ticket_id
    calls = {"n": 0}

    def counted(ticket_id: str):
        calls["n"] += 1
        return original(ticket_id)

    monkeypatch.setattr(work_order_store, "list_by_ticket_id", counted)
    body = _search(anonymous_client, "culvert").json()
    assert calls["n"] <= 3
    assert body["workOrderScanTruncated"] is True
    assert body["workOrdersTruncated"] is True
    assert body["limits"]["workOrderQueryBudget"] == 3
    assert created_ids
    exact = _search(anonymous_client, work_order.json()["workOrderId"]).json()
    assert exact["workOrders"][0]["workOrderId"] == work_order.json()["workOrderId"]
