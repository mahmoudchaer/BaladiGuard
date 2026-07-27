from app.database.memory import ticket_store
from tests.test_read_tickets import create_ticket

STAFF_ONLY_FIELDS = {
    "ticketId",
    "contact",
    "imageReferences",
    "imageObjectKey",
    "department",
    "departmentId",
    "createdBy",
    "municipalityId",
    "duplicateGroupId",
    "updatedBy",
    "ai",
    "statusHistory",
    "duplicateGroup",
    "duplicateSuggestions",
}


def test_tracking_code_lookup_returns_citizen_safe_ticket_response(client):
    created = create_ticket(client)
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    ticket_store.patch_fields(
        created["ticketId"],
        {
            "ai_suggested_category": "road_damage",
            "ai_category_explanation": "Road surface defect with traffic impact.",
            "ai_model_version": "amazon.nova-lite-v1:0",
            "category": "road_damage",
            "final_category": "road_damage",
            "department_id": "roads",
            "updated_by": "staff-1",
            "duplicate_group_id": "dup_internal",
        },
    )
    client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={
            "status": "UNDER_REVIEW",
            "updatedBy": "staff-1",
            "note": "Internal dispatch note.",
        },
    )

    response = client.get(f"/v1/tickets/track/{created['trackingCode'].lower()}")

    assert response.status_code == 200
    body = response.json()
    assert body["ticketNumber"] == created["ticketNumber"]
    assert body["trackingCode"] == created["trackingCode"]
    assert body["status"] == "UNDER_REVIEW"
    assert body["category"] == "road_damage"
    assert body["location"] == {"addressText": stored.location.address_text}
    assert body["createdAt"] == created["createdAt"]
    assert body["updatedAt"] == body["lastUpdatedAt"]
    assert [entry["status"] for entry in body["timeline"]] == ["SUBMITTED", "UNDER_REVIEW"]
    assert all(set(entry) == {"status", "changedAt"} for entry in body["timeline"])
    assert STAFF_ONLY_FIELDS.isdisjoint(body)
    assert "latitude" not in body["location"]
    assert "longitude" not in body["location"]


def test_tracking_code_lookup_returns_404_for_unknown_code(client):
    response = client.get("/v1/tickets/track/MISSING")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TICKET_NOT_FOUND"
