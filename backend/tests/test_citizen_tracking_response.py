from app.database.memory import ticket_store
from tests.test_read_tickets import create_ticket

STAFF_ONLY_FIELDS = {
    "ticketId",
    "contact",
    "imageReferences",
    "imageObjectKey",
    "departmentId",
    "createdBy",
    "municipalityId",
    "duplicateGroupId",
    "updatedBy",
    "ai",
    "statusHistory",
    "auditHistory",
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
            "department_id": "d1111111-1111-1111-1111-111111111111",
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
    assert body["department"] is None
    assert body["createdAt"] == created["createdAt"]
    assert body["updatedAt"] == body["lastUpdatedAt"]
    assert [entry["status"] for entry in body["timeline"]] == ["SUBMITTED", "UNDER_REVIEW"]
    assert all(set(entry) == {"status", "changedAt"} for entry in body["timeline"])
    assert STAFF_ONLY_FIELDS.isdisjoint(body)
    assert "latitude" not in body["location"]
    assert "longitude" not in body["location"]


def test_tracking_code_lookup_shows_name_only_department_after_assignment(client):
    created = create_ticket(client)
    ticket_store.patch_fields(
        created["ticketId"],
        {
            "category": "road_damage",
            "final_category": "road_damage",
            "department_id": "d1111111-1111-1111-1111-111111111111",
            "status": "ASSIGNED",
        },
    )

    response = client.get(f"/v1/tickets/track/{created['trackingCode']}")

    assert response.status_code == 200
    body = response.json()
    assert body["department"] == {"name": "Road Maintenance"}
    assert "departmentId" not in body
    assert "updatedBy" not in body


def test_tracking_code_lookup_hides_category_until_staff_approval(client):
    created = create_ticket(client)
    ticket_store.patch_fields(
        created["ticketId"],
        {
            "category": "road_damage",
            "final_category": None,
        },
    )

    response = client.get(f"/v1/tickets/track/{created['trackingCode']}")

    assert response.status_code == 200
    assert response.json()["category"] is None


def test_tracking_code_lookup_returns_404_for_unknown_code(client):
    # Valid format, unknown value — must not collide with format validation.
    response = client.get("/v1/tickets/track/ZZZZZZ")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_tracking_code_lookup_rejects_invalid_format(client):
    invalid_codes = [
        "AB12",  # too short
        "AB12CDE",  # too long
        "IIIIII",  # excluded ambiguous letters
        "AB12O1",  # excluded O/1
        "AB12!!",  # punctuation
    ]

    for tracking_code in invalid_codes:
        response = client.get(f"/v1/tickets/track/{tracking_code}")

        assert response.status_code == 400, tracking_code
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR", tracking_code
        assert any(detail["field"] == "trackingCode" for detail in body["error"]["details"])
        # Invalid lookups must not leak ticket payloads.
        assert STAFF_ONLY_FIELDS.isdisjoint(body)
        assert "ticketNumber" not in body
