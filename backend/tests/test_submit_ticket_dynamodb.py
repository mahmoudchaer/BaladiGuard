"""HTTP submit → DynamoDB persist → get-by-ID coverage for issue #9."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.main import app
from app.schemas.stored_ticket import PENDING_CLASSIFICATION
from app.services.complaints.ticket_service import ticket_service
from tests.test_submit_ticket import VALID_PAYLOAD


def test_submit_ticket_persists_in_dynamodb_and_is_retrievable_by_id(
    dynamodb_settings: Settings,
) -> None:
    store = DynamoTicketStore(dynamodb_settings)
    original_store = ticket_service._store
    ticket_service._store = store

    try:
        client = TestClient(app)

        response = client.post("/v1/tickets", json=VALID_PAYLOAD)

        assert response.status_code == 201
        body = response.json()
        assert body["ticketId"].startswith("tkt_")
        assert body["ticketNumber"].startswith("BG-")
        assert body["status"] == "SUBMITTED"
        assert body["createdAt"].endswith("Z")

        stored = store.get(body["ticketId"])
        assert stored is not None
        assert stored.description == VALID_PAYLOAD["description"]
        assert stored.contact.phone == VALID_PAYLOAD["contact"]["phone"]
        assert stored.contact.email == VALID_PAYLOAD["contact"]["email"]
        assert stored.location.latitude == VALID_PAYLOAD["location"]["latitude"]
        assert stored.location.longitude == VALID_PAYLOAD["location"]["longitude"]
        assert stored.location.address_text == VALID_PAYLOAD["location"]["addressText"]
        assert stored.image_object_key == VALID_PAYLOAD["imageObjectKey"]
        assert stored.status == "SUBMITTED"
        assert stored.category == PENDING_CLASSIFICATION
        assert stored.created_at == body["createdAt"]
        assert stored.updated_at == body["createdAt"]

        get_response = client.get(f"/v1/tickets/{body['ticketId']}")
        assert get_response.status_code == 200
        retrieved = get_response.json()
        assert retrieved["ticketId"] == body["ticketId"]
        assert retrieved["ticketNumber"] == body["ticketNumber"]
        assert retrieved["status"] == "SUBMITTED"
        assert retrieved["imageObjectKey"] == VALID_PAYLOAD["imageObjectKey"]
        assert retrieved["imageReferences"][0]["objectKey"] == VALID_PAYLOAD["imageObjectKey"]
        assert retrieved["createdAt"] == body["createdAt"]
        assert retrieved["updatedAt"] == body["createdAt"]
        assert retrieved["description"] == VALID_PAYLOAD["description"]
    finally:
        ticket_service._store = original_store
