from app.config import Settings
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.database.memory import ticket_store
from app.schemas.ticket_ai_update import SaveTicketAiOutputRequest
from app.services.complaints.ticket_service import ticket_service
from tests.test_read_tickets import create_ticket
from tests.test_submit_ticket import VALID_PAYLOAD

ROAD_MAINTENANCE = "d1111111-1111-1111-1111-111111111111"
WASTE_MANAGEMENT = "d2222222-2222-2222-2222-222222222222"
STREET_LIGHTING = "d3333333-3333-3333-3333-333333333333"


def _test_client():
    try:
        from tests.conftest import authenticated_test_client

        return authenticated_test_client()
    except ImportError:
        from fastapi.testclient import TestClient

        from app.main import app

        return TestClient(app)


def seed_ai_suggestion(ticket_id: str, category: str = "road_damage") -> None:
    ticket_service.save_ticket_ai_output(
        ticket_id,
        SaveTicketAiOutputRequest(
            cleanedDescription="Large pothole near the university gate.",
            aiSuggestedCategory=category,
            aiCategoryExplanation="The report describes damage to a public road.",
            aiProcessingStatus="completed",
        ),
    )


def test_assign_department_persists_and_preserves_suggestion(client):
    created = create_ticket(client)
    seed_ai_suggestion(created["ticketId"], category="road_damage")

    stored_before = ticket_store.get(created["ticketId"])
    assert stored_before is not None
    assert stored_before.department_id == ROAD_MAINTENANCE
    assert stored_before.suggested_department_id == ROAD_MAINTENANCE

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/department",
        json={"departmentId": STREET_LIGHTING, "updatedBy": "staff-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["departmentId"] == STREET_LIGHTING
    assert body["department"] == {
        "departmentId": STREET_LIGHTING,
        "name": "Street Lighting",
    }
    assert body["updatedBy"] == "staff-1"
    assert body["ai"]["suggestedDepartmentId"] == ROAD_MAINTENANCE

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.department_id == STREET_LIGHTING
    assert stored.suggested_department_id == ROAD_MAINTENANCE

    listed = client.get("/v1/tickets").json()
    match = next(ticket for ticket in listed if ticket["ticketId"] == created["ticketId"])
    assert match["departmentId"] == STREET_LIGHTING
    assert match["ai"]["suggestedDepartmentId"] == ROAD_MAINTENANCE

    detail = client.get(f"/v1/tickets/{created['ticketId']}").json()
    assert detail["departmentId"] == STREET_LIGHTING
    assert detail["ai"]["suggestedDepartmentId"] == ROAD_MAINTENANCE


def test_assign_department_rejects_unknown_department(client):
    created = create_ticket(client)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/department",
        json={"departmentId": "not-a-department"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == "departmentId" for detail in body["error"]["details"])


def test_assign_department_returns_404_for_missing_ticket(client):
    response = client.patch(
        "/v1/tickets/tkt_missing/department",
        json={"departmentId": WASTE_MANAGEMENT},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_staff_override_keeps_suggestion_when_category_changes(client):
    created = create_ticket(client)
    seed_ai_suggestion(created["ticketId"], category="road_damage")

    assign = client.patch(
        f"/v1/tickets/{created['ticketId']}/department",
        json={"departmentId": STREET_LIGHTING, "updatedBy": "staff-1"},
    )
    assert assign.status_code == 200

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/category",
        json={"finalCategory": "waste", "categoryReviewedBy": "staff-2"},
    )

    assert response.status_code == 200
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.department_id == STREET_LIGHTING
    assert stored.suggested_department_id == WASTE_MANAGEMENT
    assert response.json()["ai"]["suggestedDepartmentId"] == WASTE_MANAGEMENT


def test_assign_department_persists_in_dynamodb(dynamodb_settings: Settings) -> None:
    store = DynamoTicketStore(dynamodb_settings)
    original_store = ticket_service._store
    ticket_service._store = store

    try:
        client = _test_client()

        created = client.post("/v1/tickets", json=VALID_PAYLOAD)
        assert created.status_code == 201
        ticket_id = created.json()["ticketId"]
        seed_ai_suggestion(ticket_id, category="road_damage")

        response = client.patch(
            f"/v1/tickets/{ticket_id}/department",
            json={"departmentId": WASTE_MANAGEMENT, "updatedBy": "staff-db"},
        )
        assert response.status_code == 200
        assert response.json()["departmentId"] == WASTE_MANAGEMENT
        assert response.json()["ai"]["suggestedDepartmentId"] == ROAD_MAINTENANCE

        loaded = store.get(ticket_id)
        assert loaded is not None
        assert loaded.department_id == WASTE_MANAGEMENT
        assert loaded.suggested_department_id == ROAD_MAINTENANCE
    finally:
        ticket_service._store = original_store


def test_staff_actor_dep_is_exported_for_issue_72() -> None:
    from app.api.deps import StaffActorDep, require_staff_actor

    assert callable(require_staff_actor)
    assert StaffActorDep is not None
