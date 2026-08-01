from app.config import Settings
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.database.memory import ticket_store
from app.schemas.ticket_ai_update import ReviewTicketCategoryRequest, SaveTicketAiOutputRequest
from app.services.complaints.ticket_service import TicketNotFoundError, ticket_service
from tests.conftest import authenticated_test_client, contribution_ready_auth_headers
from tests.test_read_tickets import create_ticket
from tests.test_submit_ticket import VALID_PAYLOAD


def test_submit_ticket_processes_ai_without_overwriting_original_description(client):
    created = create_ticket(client)

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.description == VALID_PAYLOAD["description"]
    assert stored.original_description == VALID_PAYLOAD["description"]
    assert stored.ai_processing_status == "completed"
    assert stored.cleaned_description == VALID_PAYLOAD["description"]
    assert stored.ai_suggested_category == "road_damage"
    assert stored.final_category is None


def test_get_ticket_returns_completed_ai_fields(client):
    created = create_ticket(client)

    response = client.get(f"/v1/tickets/{created['ticketId']}")

    assert response.status_code == 200
    body = response.json()
    assert body["description"] == VALID_PAYLOAD["description"]
    assert body["ai"]["originalDescription"] == VALID_PAYLOAD["description"]
    assert body["ai"]["aiProcessingStatus"] == "completed"
    assert body["ai"]["cleanedDescription"] == VALID_PAYLOAD["description"]
    assert body["ai"]["aiSuggestedCategory"] == "road_damage"
    assert body["ai"]["finalCategory"] is None


def test_save_ticket_ai_output_persists_fields_without_overwriting_original(client):
    created = create_ticket(client)

    updated = ticket_service.save_ticket_ai_output(
        created["ticketId"],
        SaveTicketAiOutputRequest(
            cleanedDescription="Large pothole on Bliss Street near AUB main gate.",
            aiSuggestedCategory="road_damage",
            aiCategoryExplanation="Road surface defect with traffic impact.",
            aiModelVersion="amazon.nova-lite-v1:0",
            aiProcessingStatus="completed",
        ),
    )

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.description == VALID_PAYLOAD["description"]
    assert stored.original_description == VALID_PAYLOAD["description"]
    assert stored.cleaned_description == "Large pothole on Bliss Street near AUB main gate."
    assert stored.ai_suggested_category == "road_damage"
    assert stored.ai_category_explanation == "Road surface defect with traffic impact."
    assert stored.ai_model_version == "amazon.nova-lite-v1:0"
    assert stored.ai_processing_status == "completed"
    assert stored.ai_confidence is None
    assert stored.final_category is None
    assert stored.category == "PENDING_CLASSIFICATION"
    assert stored.department_id == "d1111111-1111-1111-1111-111111111111"
    assert stored.suggested_department_id == "d1111111-1111-1111-1111-111111111111"

    assert updated.ai is not None
    assert updated.department_id == "d1111111-1111-1111-1111-111111111111"
    assert updated.department is not None
    assert updated.department.name == "Road Maintenance"
    assert updated.ai.suggested_department_id == "d1111111-1111-1111-1111-111111111111"
    assert updated.ai.cleaned_description == stored.cleaned_description
    assert updated.ai.ai_suggested_category == "road_damage"
    assert updated.ai.suggested_category == "road_damage"
    assert updated.ai.ai_processing_status == "completed"


def test_save_ticket_ai_output_stores_confidence_only_when_provided(client):
    created = create_ticket(client)

    ticket_service.save_ticket_ai_output(
        created["ticketId"],
        SaveTicketAiOutputRequest(
            cleanedDescription="Overflowing garbage bins near the school in Mar Elias.",
            aiSuggestedCategory="waste",
            aiCategoryExplanation="Overflowing garbage bins and odor.",
            aiConfidence=0.91,
            aiProcessingStatus="completed",
        ),
    )

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.ai_confidence == 0.91


def test_save_ticket_ai_output_keeps_existing_department_for_manual_override_path(client):
    created = create_ticket(client)
    ticket_store.patch_fields(
        created["ticketId"],
        {"department_id": "d2222222-2222-2222-2222-222222222222"},
    )

    ticket_service.save_ticket_ai_output(
        created["ticketId"],
        SaveTicketAiOutputRequest(
            aiSuggestedCategory="road_damage",
            aiProcessingStatus="completed",
        ),
    )

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.department_id == "d2222222-2222-2222-2222-222222222222"


def test_save_ticket_ai_output_refreshes_auto_department_when_ai_category_changes(client):
    created = create_ticket(client)

    ticket_service.save_ticket_ai_output(
        created["ticketId"],
        SaveTicketAiOutputRequest(
            aiSuggestedCategory="road_damage",
            aiProcessingStatus="completed",
        ),
    )
    ticket_service.save_ticket_ai_output(
        created["ticketId"],
        SaveTicketAiOutputRequest(
            aiSuggestedCategory="waste",
            aiProcessingStatus="completed",
        ),
    )

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.ai_suggested_category == "waste"
    assert stored.department_id == "d2222222-2222-2222-2222-222222222222"


def test_save_ticket_ai_output_keeps_manual_department_when_ai_category_changes(client):
    created = create_ticket(client)

    ticket_service.save_ticket_ai_output(
        created["ticketId"],
        SaveTicketAiOutputRequest(
            aiSuggestedCategory="road_damage",
            aiProcessingStatus="completed",
        ),
    )
    ticket_store.patch_fields(
        created["ticketId"],
        {"department_id": "d3333333-3333-3333-3333-333333333333"},
    )

    ticket_service.save_ticket_ai_output(
        created["ticketId"],
        SaveTicketAiOutputRequest(
            aiSuggestedCategory="waste",
            aiProcessingStatus="completed",
        ),
    )

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.ai_suggested_category == "waste"
    assert stored.department_id == "d3333333-3333-3333-3333-333333333333"


def test_save_ticket_ai_output_can_record_failed_processing(client):
    created = create_ticket(client)

    ticket_service.save_ticket_ai_output(
        created["ticketId"],
        SaveTicketAiOutputRequest(aiProcessingStatus="failed"),
    )

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.description == VALID_PAYLOAD["description"]
    assert stored.ai_processing_status == "failed"
    assert stored.cleaned_description is None


def test_review_ticket_category_sets_final_without_overwriting_ai_suggestion(client):
    created = create_ticket(client)
    ticket_service.save_ticket_ai_output(
        created["ticketId"],
        SaveTicketAiOutputRequest(
            cleanedDescription="Large pothole on Bliss Street near AUB main gate.",
            aiSuggestedCategory="road_damage",
            aiCategoryExplanation="Road surface defect with traffic impact.",
            aiProcessingStatus="completed",
        ),
    )

    reviewed = ticket_service.review_ticket_category(
        created["ticketId"],
        ReviewTicketCategoryRequest(
            finalCategory="waste",
            categoryReviewedBy="staff-1",
        ),
    )

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.description == VALID_PAYLOAD["description"]
    assert stored.original_description == VALID_PAYLOAD["description"]
    assert stored.cleaned_description == "Large pothole on Bliss Street near AUB main gate."
    assert stored.ai_suggested_category == "road_damage"
    assert stored.final_category == "waste"
    assert stored.category == "waste"
    assert stored.category_reviewed_by == "staff-1"
    assert stored.category_reviewed_at is not None

    assert reviewed.ai is not None
    assert reviewed.ai.ai_suggested_category == "road_damage"
    assert reviewed.ai.final_category == "waste"
    assert reviewed.ai.category_reviewed_by == "staff-1"
    assert reviewed.category == "waste"


def test_save_ticket_ai_output_raises_for_unknown_ticket():
    try:
        ticket_service.save_ticket_ai_output(
            "tkt_missing",
            SaveTicketAiOutputRequest(aiProcessingStatus="failed"),
        )
    except TicketNotFoundError:
        pass
    else:
        raise AssertionError("Expected TicketNotFoundError")


def test_list_tickets_includes_ai_fields(client):
    created = create_ticket(client)
    ticket_service.save_ticket_ai_output(
        created["ticketId"],
        SaveTicketAiOutputRequest(
            cleanedDescription="Large pothole on Bliss Street near AUB main gate.",
            aiSuggestedCategory="road_damage",
            aiCategoryExplanation="Road surface defect with traffic impact.",
            aiProcessingStatus="completed",
        ),
    )

    response = client.get("/v1/tickets")

    assert response.status_code == 200
    ticket = next(item for item in response.json() if item["ticketId"] == created["ticketId"])
    assert ticket["ai"]["aiProcessingStatus"] == "completed"
    assert ticket["ai"]["cleanedDescription"] is not None


def test_ticket_ai_fields_persist_in_dynamodb(dynamodb_settings: Settings) -> None:
    store = DynamoTicketStore(dynamodb_settings)
    original_store = ticket_service._store
    ticket_service._store = store

    try:
        client = authenticated_test_client()
        response = client.post("/v1/tickets", json=VALID_PAYLOAD, headers=contribution_ready_auth_headers())
        assert response.status_code == 201
        ticket_id = response.json()["ticketId"]

        ticket_service.save_ticket_ai_output(
            ticket_id,
            SaveTicketAiOutputRequest(
                cleanedDescription="Large pothole on Bliss Street near AUB main gate.",
                aiSuggestedCategory="road_damage",
                aiCategoryExplanation="Road surface defect with traffic impact.",
                aiModelVersion="amazon.nova-lite-v1:0",
                aiProcessingStatus="completed",
            ),
        )

        stored = store.get(ticket_id)
        assert stored is not None
        assert stored.original_description == VALID_PAYLOAD["description"]
        assert stored.cleaned_description is not None
        assert stored.ai_suggested_category == "road_damage"
        assert stored.ai_processing_status == "completed"

        get_response = client.get(f"/v1/tickets/{ticket_id}")
        assert get_response.status_code == 200
        body = get_response.json()
        assert body["ai"]["cleanedDescription"] == stored.cleaned_description
        assert body["ai"]["aiSuggestedCategory"] == "road_damage"
        assert body["ai"]["aiProcessingStatus"] == "completed"
    finally:
        ticket_service._store = original_store
