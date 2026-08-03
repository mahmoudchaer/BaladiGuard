"""Status update coverage with DynamoDB persistence."""

from app.config import Settings
from app.database.dynamo_status_history_store import DynamoStatusHistoryStore
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.services.complaints.ticket_service import ticket_service
from tests.conftest import authenticated_test_client, contribution_ready_auth_headers
from tests.test_submit_ticket import VALID_PAYLOAD

ADMIN_STAFF_ID = "staff_admin_001"


def test_update_ticket_status_persists_history_in_dynamodb(dynamodb_settings: Settings) -> None:
    store = DynamoTicketStore(dynamodb_settings)
    history_store = DynamoStatusHistoryStore(dynamodb_settings)
    original_store = ticket_service._store
    original_history_store = ticket_service._history_store
    ticket_service._store = store
    ticket_service._history_store = history_store

    try:
        client = authenticated_test_client()
        submit_response = client.post(
            "/v1/tickets", json=VALID_PAYLOAD, headers=contribution_ready_auth_headers()
        )
        assert submit_response.status_code == 201
        ticket_id = submit_response.json()["ticketId"]

        update_response = client.patch(
            f"/v1/tickets/{ticket_id}/status",
            json={"status": "UNDER_REVIEW", "updatedBy": "staff-dynamo"},
        )
        assert update_response.status_code == 200
        body = update_response.json()
        assert body["status"] == "UNDER_REVIEW"
        assert body["updatedBy"] == ADMIN_STAFF_ID
        assert len(body["statusHistory"]) == 2

        stored = store.get(ticket_id)
        assert stored is not None
        assert stored.status == "UNDER_REVIEW"
        assert stored.updated_by == ADMIN_STAFF_ID

        history = history_store.list_by_ticket_id(ticket_id)
        assert len(history) == 2
        assert history[0].new_status == "SUBMITTED"
        assert history[1].new_status == "UNDER_REVIEW"
        assert history[1].updated_by == ADMIN_STAFF_ID
    finally:
        ticket_service._store = original_store
        ticket_service._history_store = original_history_store
