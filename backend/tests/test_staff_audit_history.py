"""Staff audit history for ticket mutations (issue #143)."""

from app.config import Settings
from app.database.dynamo_audit_history_store import DynamoAuditHistoryStore
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.database.memory_audit_history import audit_history_store
from app.database.memory_status_history import status_history_store
from app.services.complaints.ticket_service import ticket_service
from tests.conftest import contribution_ready_auth_headers
from tests.test_read_tickets import create_ticket
from tests.test_submit_ticket import VALID_PAYLOAD

ROAD_MAINTENANCE = "d1111111-1111-1111-1111-111111111111"
WASTE_MANAGEMENT = "d2222222-2222-2222-2222-222222222222"
ADMIN_STAFF_ID = "staff_admin_001"


def _audit_by_type(body: dict, action_type: str) -> list[dict]:
    return [entry for entry in body.get("auditHistory", []) if entry["actionType"] == action_type]


def test_status_change_writes_audit_and_keeps_status_history(client):
    created = create_ticket(client)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "UNDER_REVIEW", "updatedBy": "staff-1", "note": "Queued for review."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["statusHistory"][-1]["status"] == "UNDER_REVIEW"
    audits = _audit_by_type(body, "STATUS_CHANGE")
    assert len(audits) == 1
    assert audits[0] == {
        "actionType": "STATUS_CHANGE",
        "actorId": ADMIN_STAFF_ID,
        "actorRole": "administrator",
        "summary": "Status changed from SUBMITTED to UNDER_REVIEW.",
        "previousValue": "SUBMITTED",
        "newValue": "UNDER_REVIEW",
        "changedAt": body["updatedAt"],
    }


def test_category_review_writes_audit_record(client):
    created = create_ticket(client)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/category",
        json={"finalCategory": "waste", "categoryReviewedBy": "staff-2"},
    )

    assert response.status_code == 200
    body = response.json()
    audits = _audit_by_type(body, "CATEGORY_REVIEW")
    assert len(audits) == 1
    assert audits[0]["actorId"] == ADMIN_STAFF_ID
    assert audits[0]["actorRole"] == "administrator"
    assert audits[0]["newValue"] == "waste"
    assert audits[0]["previousValue"] in {"PENDING_CLASSIFICATION", "road_damage"}
    assert "Category reviewed as waste." in audits[0]["summary"]


def test_department_assignment_writes_audit_record(client):
    created = create_ticket(client)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/department",
        json={"departmentId": WASTE_MANAGEMENT, "updatedBy": "staff-3"},
    )

    assert response.status_code == 200
    body = response.json()
    audits = _audit_by_type(body, "DEPARTMENT_ASSIGN")
    assert len(audits) == 1
    assert audits[0]["actorId"] == ADMIN_STAFF_ID
    assert audits[0]["actorRole"] == "administrator"
    assert audits[0]["previousValue"] == ROAD_MAINTENANCE
    assert audits[0]["newValue"] == WASTE_MANAGEMENT
    assert audits[0]["summary"].startswith("Department assignment changed from")


def test_duplicate_merge_writes_audit_for_canonical_and_duplicate(client):
    main = create_ticket(client, "Main road damage report near the gate.")
    duplicate = create_ticket(client, "Duplicate road damage report near the same gate.")

    response = client.post(
        "/v1/tickets/merge",
        json={
            "canonicalTicketId": main["ticketId"],
            "duplicateTicketIds": [duplicate["ticketId"]],
            "mergedBy": "staff-4",
        },
    )

    assert response.status_code == 200
    body = response.json()
    canonical_audits = _audit_by_type(body, "DUPLICATE_MERGE")
    assert len(canonical_audits) == 1
    assert canonical_audits[0]["actorId"] == ADMIN_STAFF_ID
    assert canonical_audits[0]["actorRole"] == "administrator"
    assert canonical_audits[0]["previousValue"] is None
    assert canonical_audits[0]["newValue"] == body["duplicateGroupId"]
    assert "canonical" in canonical_audits[0]["summary"]

    duplicate_detail = client.get(f"/v1/tickets/{duplicate['ticketId']}")
    assert duplicate_detail.status_code == 200
    duplicate_audits = _audit_by_type(duplicate_detail.json(), "DUPLICATE_MERGE")
    assert len(duplicate_audits) == 1
    assert duplicate_audits[0]["actorId"] == ADMIN_STAFF_ID
    assert "duplicate" in duplicate_audits[0]["summary"]
    assert duplicate_audits[0]["newValue"] == body["duplicateGroupId"]


def test_ticket_detail_exposes_audit_history_to_staff_only(client, anonymous_client):
    created = create_ticket(client)
    client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "UNDER_REVIEW", "updatedBy": "staff-1"},
    )

    staff_detail = client.get(f"/v1/tickets/{created['ticketId']}")
    assert staff_detail.status_code == 200
    assert _audit_by_type(staff_detail.json(), "STATUS_CHANGE")

    track = anonymous_client.get(f"/v1/tickets/track/{created['trackingCode']}")
    assert track.status_code == 200
    assert "auditHistory" not in track.json()


def test_audit_write_failure_does_not_block_primary_mutation(client, monkeypatch):
    created = create_ticket(client)

    def boom(_entry):
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(ticket_service._audit_store, "append", boom)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/department",
        json={"departmentId": WASTE_MANAGEMENT, "updatedBy": "staff-5"},
    )

    assert response.status_code == 200
    assert response.json()["departmentId"] == WASTE_MANAGEMENT
    assert response.json()["auditHistory"] == []
    assert audit_history_store.list_by_ticket_id(created["ticketId"]) == []
    # Status history remains independent and still works for status updates.
    assert status_history_store.list_by_ticket_id(created["ticketId"])


def test_audit_read_failure_does_not_block_primary_mutation_response(client, monkeypatch):
    created = create_ticket(client)

    def boom_list(_ticket_id):
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(ticket_service._audit_store, "list_by_ticket_id", boom_list)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "UNDER_REVIEW", "updatedBy": "staff-6"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "UNDER_REVIEW"
    assert response.json()["auditHistory"] == []
    # Primary status history still maps successfully.
    assert response.json()["statusHistory"][-1]["status"] == "UNDER_REVIEW"

    detail = client.get(f"/v1/tickets/{created['ticketId']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "UNDER_REVIEW"
    assert detail.json()["auditHistory"] == []


def test_audit_history_persists_in_dynamodb(dynamodb_settings: Settings) -> None:
    ticket_store = DynamoTicketStore(dynamodb_settings)
    audit_store = DynamoAuditHistoryStore(dynamodb_settings)
    original_ticket_store = ticket_service._store
    original_audit_store = ticket_service._audit_store
    ticket_service._store = ticket_store
    ticket_service._audit_store = audit_store

    try:
        from tests.conftest import authenticated_test_client

        client = authenticated_test_client()
        created = client.post(
            "/v1/tickets",
            json={**VALID_PAYLOAD, "description": "DynamoDB audit history ticket."},
            headers=contribution_ready_auth_headers(),
        )
        assert created.status_code == 201
        ticket_id = created.json()["ticketId"]

        response = client.patch(
            f"/v1/tickets/{ticket_id}/status",
            json={"status": "UNDER_REVIEW", "updatedBy": "staff-db"},
        )
        assert response.status_code == 200
        assert _audit_by_type(response.json(), "STATUS_CHANGE")

        persisted = audit_store.list_by_ticket_id(ticket_id)
        assert len(persisted) == 1
        assert persisted[0].action_type == "STATUS_CHANGE"
        assert persisted[0].actor_id == ADMIN_STAFF_ID
        assert persisted[0].previous_value == "SUBMITTED"
        assert persisted[0].new_value == "UNDER_REVIEW"
    finally:
        ticket_service._store = original_ticket_store
        ticket_service._audit_store = original_audit_store
