"""Ticket list query filters for urgency, department, status, and category (issue #142)."""

from app.config import Settings
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.database.memory import ticket_store
from app.services.complaints.ticket_list_filters import (
    TicketListFilters,
    filter_stored_tickets,
    parse_ticket_list_filters,
)
from app.services.complaints.ticket_service import ticket_service
from tests.test_read_tickets import create_ticket
from tests.test_submit_ticket import VALID_PAYLOAD

ROAD_MAINTENANCE = "d1111111-1111-1111-1111-111111111111"
WASTE_MANAGEMENT = "d2222222-2222-2222-2222-222222222222"
STREET_LIGHTING = "d3333333-3333-3333-3333-333333333333"


def _seed_ticket(
    client,
    *,
    description: str,
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    department_id: str | None = None,
) -> dict:
    created = create_ticket(client, description)
    ticket_id = created["ticketId"]
    fields: dict[str, object] = {}
    if status is not None:
        fields["status"] = status
    if category is not None:
        fields["category"] = category
    if priority is not None:
        fields["priority"] = priority
    if department_id is not None:
        fields["department_id"] = department_id
    if fields:
        patched = ticket_store.patch_fields(ticket_id, fields)
        assert patched is not None
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    return {
        "ticketId": ticket_id,
        "status": stored.status,
        "category": stored.category,
        "priority": stored.priority,
        "departmentId": stored.department_id,
    }


def test_parse_ticket_list_filters_accepts_valid_values():
    filters, errors = parse_ticket_list_filters(
        status="IN_PROGRESS",
        category="waste",
        urgency="HIGH",
        department_id=WASTE_MANAGEMENT,
    )
    assert errors == []
    assert filters == TicketListFilters(
        status="IN_PROGRESS",
        category="waste",
        urgency="high",
        department_id=WASTE_MANAGEMENT,
    )


def test_parse_ticket_list_filters_rejects_invalid_and_blank_values():
    filters, errors = parse_ticket_list_filters(
        status=" ",
        category="not-a-category",
        urgency="urgent",
        department_id="not-a-department",
    )
    assert filters is None
    fields = {error.field for error in errors}
    assert fields == {"status", "category", "urgency", "departmentId"}


def test_filter_stored_tickets_and_combines_fields(client):
    matching = _seed_ticket(
        client,
        description="Matching waste ticket for combined filters.",
        status="IN_PROGRESS",
        category="waste",
        priority="high",
        department_id=WASTE_MANAGEMENT,
    )
    _seed_ticket(
        client,
        description="Wrong department for combined filters.",
        status="IN_PROGRESS",
        category="waste",
        priority="high",
        department_id=ROAD_MAINTENANCE,
    )
    _seed_ticket(
        client,
        description="Wrong urgency for combined filters.",
        status="IN_PROGRESS",
        category="waste",
        priority="low",
        department_id=WASTE_MANAGEMENT,
    )

    filters = TicketListFilters(
        status="IN_PROGRESS",
        category="waste",
        urgency="high",
        department_id=WASTE_MANAGEMENT,
    )
    matched = filter_stored_tickets(ticket_store.list(), filters)
    assert [ticket.ticket_id for ticket in matched] == [matching["ticketId"]]


def test_list_tickets_filters_by_urgency(client):
    high = _seed_ticket(
        client,
        description="High urgency pothole near a busy intersection.",
        priority="high",
    )
    _seed_ticket(
        client,
        description="Low urgency faded paint on a quiet street.",
        priority="low",
    )
    ticket_store.patch_fields(high["ticketId"], {"priority": "high"})
    null_priority = create_ticket(client, "Ticket waiting for urgency estimation.")
    ticket_store.patch_fields(null_priority["ticketId"], {"priority": None})

    response = client.get("/v1/tickets", params={"urgency": "high"})

    assert response.status_code == 200
    body = response.json()
    assert [ticket["ticketId"] for ticket in body] == [high["ticketId"]]
    assert all(ticket["priority"] == "high" for ticket in body)


def test_list_tickets_filters_by_department(client):
    waste = _seed_ticket(
        client,
        description="Overflowing bins that need waste collection.",
        department_id=WASTE_MANAGEMENT,
    )
    _seed_ticket(
        client,
        description="Broken street lamp after midnight.",
        department_id=STREET_LIGHTING,
    )

    response = client.get("/v1/tickets", params={"departmentId": WASTE_MANAGEMENT})

    assert response.status_code == 200
    body = response.json()
    assert [ticket["ticketId"] for ticket in body] == [waste["ticketId"]]
    assert all(ticket["departmentId"] == WASTE_MANAGEMENT for ticket in body)


def test_list_tickets_filters_by_status_and_category(client):
    matching = _seed_ticket(
        client,
        description="Resolved sidewalk issue after staff review.",
        status="RESOLVED",
        category="sidewalk_damage",
    )
    _seed_ticket(
        client,
        description="Open sidewalk issue still in progress.",
        status="IN_PROGRESS",
        category="sidewalk_damage",
    )
    _seed_ticket(
        client,
        description="Resolved waste issue in another category.",
        status="RESOLVED",
        category="waste",
    )

    response = client.get(
        "/v1/tickets",
        params={"status": "RESOLVED", "category": "sidewalk_damage"},
    )

    assert response.status_code == 200
    body = response.json()
    assert [ticket["ticketId"] for ticket in body] == [matching["ticketId"]]


def test_list_tickets_combines_urgency_department_status_and_category(client):
    matching = _seed_ticket(
        client,
        description="Critical waste ticket assigned and in progress.",
        status="IN_PROGRESS",
        category="waste",
        priority="critical",
        department_id=WASTE_MANAGEMENT,
    )
    _seed_ticket(
        client,
        description="Same filters except department.",
        status="IN_PROGRESS",
        category="waste",
        priority="critical",
        department_id=ROAD_MAINTENANCE,
    )

    response = client.get(
        "/v1/tickets",
        params={
            "status": "IN_PROGRESS",
            "category": "waste",
            "urgency": "critical",
            "departmentId": WASTE_MANAGEMENT,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [ticket["ticketId"] for ticket in body] == [matching["ticketId"]]


def test_list_tickets_returns_empty_list_when_filters_match_nothing(client):
    _seed_ticket(
        client,
        description="Only a road maintenance ticket exists.",
        department_id=ROAD_MAINTENANCE,
        priority="medium",
    )

    response = client.get(
        "/v1/tickets",
        params={"urgency": "critical", "departmentId": STREET_LIGHTING},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_tickets_rejects_invalid_filter_values(client):
    response = client.get(
        "/v1/tickets",
        params={
            "status": "DONE",
            "category": "unknown",
            "urgency": "severe",
            "departmentId": "dept_missing",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    fields = {detail["field"] for detail in body["error"]["details"]}
    assert fields == {"status", "category", "urgency", "departmentId"}


def test_list_tickets_rejects_blank_filter_values(client):
    response = client.get(
        "/v1/tickets",
        params={"urgency": "   ", "departmentId": ""},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    fields = {detail["field"] for detail in body["error"]["details"]}
    assert "urgency" in fields
    assert "departmentId" in fields


def test_list_tickets_without_filters_still_returns_all(client):
    first = create_ticket(client, "First unfiltered ticket.")
    second = create_ticket(client, "Second unfiltered ticket.")

    response = client.get("/v1/tickets")

    assert response.status_code == 200
    assert [ticket["ticketId"] for ticket in response.json()] == [
        second["ticketId"],
        first["ticketId"],
    ]


def test_list_tickets_filters_work_in_dynamodb(dynamodb_settings: Settings) -> None:
    store = DynamoTicketStore(dynamodb_settings)
    original_store = ticket_service._store
    ticket_service._store = store

    try:
        from tests.conftest import authenticated_test_client

        client = authenticated_test_client()

        created = client.post(
            "/v1/tickets",
            json={
                **VALID_PAYLOAD,
                "description": "DynamoDB filter candidate for waste department.",
            },
        )
        assert created.status_code == 201
        ticket_id = created.json()["ticketId"]

        patched = store.patch_fields(
            ticket_id,
            {
                "status": "ASSIGNED",
                "category": "waste",
                "priority": "high",
                "department_id": WASTE_MANAGEMENT,
            },
        )
        assert patched is not None

        other = client.post(
            "/v1/tickets",
            json={
                **VALID_PAYLOAD,
                "description": "DynamoDB ticket that should be excluded by filters.",
            },
        )
        assert other.status_code == 201
        store.patch_fields(
            other.json()["ticketId"],
            {
                "status": "ASSIGNED",
                "category": "waste",
                "priority": "low",
                "department_id": ROAD_MAINTENANCE,
            },
        )

        response = client.get(
            "/v1/tickets",
            params={
                "status": "ASSIGNED",
                "category": "waste",
                "urgency": "high",
                "departmentId": WASTE_MANAGEMENT,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert [ticket["ticketId"] for ticket in body] == [ticket_id]

        empty = client.get(
            "/v1/tickets",
            params={"urgency": "critical", "departmentId": STREET_LIGHTING},
        )
        assert empty.status_code == 200
        assert empty.json() == []
    finally:
        ticket_service._store = original_store
