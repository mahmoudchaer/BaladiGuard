from fastapi.testclient import TestClient

from app.config import Settings
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.database.memory import ticket_store
from app.main import app
from app.schemas.ticket_ai_update import SaveTicketAiOutputRequest
from app.services.complaints.ticket_service import ticket_service
from tests.test_read_tickets import create_ticket
from tests.test_submit_ticket import VALID_PAYLOAD


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


def test_accept_ai_suggestion_through_api_preserves_original_ai_fields(client):
    created = create_ticket(client)
    seed_ai_suggestion(created["ticketId"])

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/category",
        json={"finalCategory": "road_damage", "categoryReviewedBy": "staff-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "road_damage"
    assert body["updatedBy"] == "staff-1"
    assert body["ai"]["aiSuggestedCategory"] == "road_damage"
    assert body["ai"]["aiCategoryExplanation"] == ("The report describes damage to a public road.")
    assert body["ai"]["finalCategory"] == "road_damage"
    assert body["ai"]["categoryReviewedBy"] == "staff-1"
    assert body["ai"]["categoryReviewedAt"] is not None

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.original_description == VALID_PAYLOAD["description"]
    assert stored.ai_suggested_category == "road_damage"
    assert stored.final_category == "road_damage"


def test_staff_can_correct_ai_suggestion_to_another_supported_category(client):
    created = create_ticket(client)
    seed_ai_suggestion(created["ticketId"])

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/category",
        json={"finalCategory": "waste", "categoryReviewedBy": "staff-2"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "waste"
    assert body["ai"]["finalCategory"] == "waste"
    assert body["ai"]["aiSuggestedCategory"] == "road_damage"
    assert body["departmentId"] == "d2222222-2222-2222-2222-222222222222"


def test_staff_category_correction_refreshes_ai_suggested_department(client):
    created = create_ticket(client)
    seed_ai_suggestion(created["ticketId"], category="road_damage")

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/category",
        json={"finalCategory": "waste", "categoryReviewedBy": "staff-2"},
    )

    assert response.status_code == 200
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.category == "waste"
    assert stored.final_category == "waste"
    assert stored.department_id == "d2222222-2222-2222-2222-222222222222"
    assert stored.suggested_department_id == "d2222222-2222-2222-2222-222222222222"


def test_staff_category_correction_keeps_manual_department_override(client):
    created = create_ticket(client)
    seed_ai_suggestion(created["ticketId"], category="road_damage")
    ticket_store.patch_fields(
        created["ticketId"],
        {"department_id": "d3333333-3333-3333-3333-333333333333"},
    )

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/category",
        json={"finalCategory": "waste", "categoryReviewedBy": "staff-2"},
    )

    assert response.status_code == 200
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.category == "waste"
    assert stored.final_category == "waste"
    assert stored.department_id == "d3333333-3333-3333-3333-333333333333"


def test_category_review_allows_missing_reviewer_identity(client):
    created = create_ticket(client)
    seed_ai_suggestion(created["ticketId"])

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/category",
        json={"finalCategory": "road_damage"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ai"]["categoryReviewedBy"] is None
    assert body["ai"]["categoryReviewedAt"] is not None


def test_category_review_rejects_unsupported_or_pending_category(client):
    created = create_ticket(client)

    for category in ("not_a_category", "PENDING_CLASSIFICATION"):
        response = client.patch(
            f"/v1/tickets/{created['ticketId']}/category",
            json={"finalCategory": category},
        )

        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert any(detail["field"] == "finalCategory" for detail in body["error"]["details"])


def test_category_review_returns_404_for_unknown_ticket(client):
    response = client.patch(
        "/v1/tickets/tkt_missing/category",
        json={"finalCategory": "waste"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_category_review_persists_in_dynamodb(dynamodb_settings: Settings) -> None:
    store = DynamoTicketStore(dynamodb_settings)
    original_store = ticket_service._store
    ticket_service._store = store

    try:
        client = TestClient(app)
        created = client.post("/v1/tickets", json=VALID_PAYLOAD)
        assert created.status_code == 201
        ticket_id = created.json()["ticketId"]
        seed_ai_suggestion(ticket_id)

        response = client.patch(
            f"/v1/tickets/{ticket_id}/category",
            json={"finalCategory": "waste", "categoryReviewedBy": "staff-3"},
        )

        assert response.status_code == 200
        stored = store.get(ticket_id)
        assert stored is not None
        assert stored.category == "waste"
        assert stored.final_category == "waste"
        assert stored.ai_suggested_category == "road_damage"
        assert stored.category_reviewed_by == "staff-3"
        assert stored.category_reviewed_at is not None
    finally:
        ticket_service._store = original_store
