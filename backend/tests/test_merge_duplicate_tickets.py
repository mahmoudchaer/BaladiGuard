"""API tests for staff duplicate merge (issue #27)."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.database.dynamo_duplicate_group_store import DynamoDuplicateGroupStore
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.database.memory import ticket_store
from app.database.memory_duplicate_group import duplicate_group_store
from app.main import app
from app.services.complaints.ticket_service import ticket_service
from tests.test_read_tickets import create_ticket


def test_merge_duplicate_tickets_saves_group_and_links_members(client):
    main = create_ticket(client)
    duplicate = create_ticket(client)

    response = client.post(
        "/v1/tickets/merge",
        json={
            "canonicalTicketId": main["ticketId"],
            "duplicateTicketIds": [duplicate["ticketId"]],
            "mergedBy": "staff-1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ticketId"] == main["ticketId"]
    assert body["duplicateGroupId"] is not None
    assert body["duplicateGroup"]["duplicateGroupId"] == body["duplicateGroupId"]
    assert body["duplicateGroup"]["canonicalTicketId"] == main["ticketId"]
    assert body["duplicateGroup"]["ticketIds"] == [main["ticketId"], duplicate["ticketId"]]
    assert body["updatedBy"] == "staff-1"

    stored_main = ticket_store.get(main["ticketId"])
    stored_duplicate = ticket_store.get(duplicate["ticketId"])
    assert stored_main is not None
    assert stored_duplicate is not None
    assert stored_main.duplicate_group_id == body["duplicateGroupId"]
    assert stored_duplicate.duplicate_group_id == body["duplicateGroupId"]

    group = duplicate_group_store.get(body["duplicateGroupId"])
    assert group is not None
    assert group.canonical_ticket_id == main["ticketId"]
    assert group.ticket_ids == [main["ticketId"], duplicate["ticketId"]]

    detail = client.get(f"/v1/tickets/{duplicate['ticketId']}")
    assert detail.status_code == 200
    assert detail.json()["duplicateGroup"]["canonicalTicketId"] == main["ticketId"]


def test_merge_rejects_when_main_ticket_is_also_listed_as_duplicate(client):
    main = create_ticket(client)

    response = client.post(
        "/v1/tickets/merge",
        json={
            "canonicalTicketId": main["ticketId"],
            "duplicateTicketIds": [main["ticketId"]],
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_merge_returns_404_for_unknown_duplicate(client):
    main = create_ticket(client)

    response = client.post(
        "/v1/tickets/merge",
        json={
            "canonicalTicketId": main["ticketId"],
            "duplicateTicketIds": ["tkt_missing"],
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_merge_persists_group_in_moto_dynamodb(dynamodb_settings: Settings) -> None:
    store = DynamoTicketStore(dynamodb_settings)
    groups = DynamoDuplicateGroupStore(dynamodb_settings)
    original_store = ticket_service._store
    original_groups = ticket_service._duplicate_group_store
    ticket_service._store = store
    ticket_service._duplicate_group_store = groups

    try:
        client = TestClient(app)
        main = create_ticket(client)
        duplicate = create_ticket(client)

        response = client.post(
            "/v1/tickets/merge",
            json={
                "canonicalTicketId": main["ticketId"],
                "duplicateTicketIds": [duplicate["ticketId"]],
                "mergedBy": "staff-dynamo",
            },
        )

        assert response.status_code == 200
        group_id = response.json()["duplicateGroupId"]
        loaded = groups.get(group_id)
        assert loaded is not None
        assert loaded.canonical_ticket_id == main["ticketId"]
        assert store.get(main["ticketId"]).duplicate_group_id == group_id
        assert store.get(duplicate["ticketId"]).duplicate_group_id == group_id
    finally:
        ticket_service._store = original_store
        ticket_service._duplicate_group_store = original_groups
