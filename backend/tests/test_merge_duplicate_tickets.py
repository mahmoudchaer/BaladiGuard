"""API tests for staff duplicate merge (issue #27)."""

from app.config import Settings
from app.database.dynamo_duplicate_group_store import DynamoDuplicateGroupStore
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.database.memory import ticket_store
from app.database.memory_duplicate_group import duplicate_group_store
from app.services.complaints.ticket_service import ticket_service
from tests.conftest import authenticated_test_client
from tests.test_read_tickets import create_ticket

ADMIN_STAFF_ID = "staff_admin_001"


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
    assert body["updatedBy"] == ADMIN_STAFF_ID

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


def _merge(client, canonical_id: str, duplicate_ids: list[str]):
    return client.post(
        "/v1/tickets/merge",
        json={
            "canonicalTicketId": canonical_id,
            "duplicateTicketIds": duplicate_ids,
        },
    )


def _override_ticket(ticket_id: str, **fields) -> None:
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    ticket_store.save(stored.model_copy(update=fields))


def test_merge_rejects_duplicate_that_is_already_grouped(client):
    main_a = create_ticket(client)
    dup_b = create_ticket(client)
    main_c = create_ticket(client)

    assert _merge(client, main_a["ticketId"], [dup_b["ticketId"]]).status_code == 200

    response = _merge(client, main_c["ticketId"], [dup_b["ticketId"]])

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    # Existing group must be untouched.
    stored_b = ticket_store.get(dup_b["ticketId"])
    group = duplicate_group_store.get(stored_b.duplicate_group_id)
    assert group.ticket_ids == [main_a["ticketId"], dup_b["ticketId"]]


def test_merge_appends_new_duplicates_to_existing_group_of_main_ticket(client):
    main = create_ticket(client)
    first_dup = create_ticket(client)
    second_dup = create_ticket(client)

    first = _merge(client, main["ticketId"], [first_dup["ticketId"]])
    assert first.status_code == 200
    group_id = first.json()["duplicateGroupId"]

    second = _merge(client, main["ticketId"], [second_dup["ticketId"]])

    assert second.status_code == 200
    body = second.json()
    assert body["duplicateGroupId"] == group_id
    assert body["duplicateGroup"]["ticketIds"] == [
        main["ticketId"],
        first_dup["ticketId"],
        second_dup["ticketId"],
    ]
    # Every member keeps the same group; no orphans.
    for ticket_id in (main["ticketId"], first_dup["ticketId"], second_dup["ticketId"]):
        assert ticket_store.get(ticket_id).duplicate_group_id == group_id
    assert duplicate_group_store.get(group_id).ticket_ids == body["duplicateGroup"]["ticketIds"]


def test_merge_rejects_when_main_ticket_is_a_non_canonical_group_member(client):
    main = create_ticket(client)
    dup = create_ticket(client)
    extra = create_ticket(client)

    assert _merge(client, main["ticketId"], [dup["ticketId"]]).status_code == 200

    response = _merge(client, dup["ticketId"], [extra["ticketId"]])

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert main["ticketId"] in body["error"]["message"]


def test_merge_rejects_cross_category_tickets(client):
    main = create_ticket(client)
    dup = create_ticket(client)
    _override_ticket(dup["ticketId"], ai_suggested_category="waste")

    response = _merge(client, main["ticketId"], [dup["ticketId"]])

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert ticket_store.get(dup["ticketId"]).duplicate_group_id is None


def test_merge_uses_reviewed_final_category_over_ai_suggestion(client):
    main = create_ticket(client)
    dup = create_ticket(client)
    # Staff corrected both to waste even though AI said road_damage.
    _override_ticket(main["ticketId"], final_category="waste")
    _override_ticket(dup["ticketId"], final_category="waste", ai_suggested_category="lighting")

    response = _merge(client, main["ticketId"], [dup["ticketId"]])

    assert response.status_code == 200


def test_merge_rejects_pending_classification_tickets(client):
    main = create_ticket(client)
    dup = create_ticket(client)
    _override_ticket(dup["ticketId"], ai_suggested_category=None, final_category=None)

    response = _merge(client, main["ticketId"], [dup["ticketId"]])

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_merge_rolls_back_member_stamps_when_group_save_fails(client, monkeypatch):
    import pytest

    from app.schemas.ticket_merge import MergeDuplicateTicketsRequest

    main = create_ticket(client)
    dup = create_ticket(client)

    def failing_save(group):
        raise RuntimeError("simulated store outage")

    monkeypatch.setattr(ticket_service._duplicate_group_store, "save", failing_save)

    with pytest.raises(RuntimeError):
        ticket_service.merge_duplicate_tickets(
            MergeDuplicateTicketsRequest(
                canonicalTicketId=main["ticketId"],
                duplicateTicketIds=[dup["ticketId"]],
            )
        )

    # No group row saved and every member stamp rolled back.
    assert ticket_store.get(main["ticketId"]).duplicate_group_id is None
    assert ticket_store.get(dup["ticketId"]).duplicate_group_id is None


def test_ai_output_saved_after_merge_preserves_duplicate_group(client):
    from app.schemas.ticket_ai_update import SaveTicketAiOutputRequest

    main = create_ticket(client)
    dup = create_ticket(client)
    merged = _merge(client, main["ticketId"], [dup["ticketId"]])
    group_id = merged.json()["duplicateGroupId"]

    ticket_service.save_ticket_ai_output(
        dup["ticketId"],
        SaveTicketAiOutputRequest(
            cleanedDescription="Cleaned after merge.",
            aiSuggestedCategory="road_damage",
            aiProcessingStatus="completed",
        ),
    )

    stored = ticket_store.get(dup["ticketId"])
    assert stored.duplicate_group_id == group_id
    assert stored.cleaned_description == "Cleaned after merge."


def test_merge_persists_group_in_moto_dynamodb(dynamodb_settings: Settings) -> None:
    store = DynamoTicketStore(dynamodb_settings)
    groups = DynamoDuplicateGroupStore(dynamodb_settings)
    original_store = ticket_service._store
    original_groups = ticket_service._duplicate_group_store
    ticket_service._store = store
    ticket_service._duplicate_group_store = groups

    try:
        client = authenticated_test_client()
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
