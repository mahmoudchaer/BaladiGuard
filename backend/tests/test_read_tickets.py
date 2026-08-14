from app.database.memory import ticket_store
from app.services.ai_job_queue import ai_job_queue
from tests.conftest import contribution_ready_auth_headers
from tests.test_submit_ticket import VALID_PAYLOAD


def create_ticket(client, description: str = VALID_PAYLOAD["description"]) -> dict:
    payload = {**VALID_PAYLOAD, "description": description}
    response = client.post(
        "/v1/tickets",
        json=payload,
        headers=contribution_ready_auth_headers(),
    )
    assert response.status_code == 201, response.text
    assert ai_job_queue.run_once().outcome == "succeeded"
    return response.json()


def test_list_tickets_returns_submitted_tickets(client):
    first = create_ticket(
        client,
        "Large pothole reported near the university gate causing traffic disruption.",
    )
    second = create_ticket(
        client,
        "Overflowing garbage bins blocking the sidewalk and attracting pests.",
    )

    response = client.get("/v1/tickets")

    assert response.status_code == 200
    body = response.json()["items"]
    assert [ticket["ticketId"] for ticket in body] == [second["ticketId"], first["ticketId"]]
    assert [ticket["createdAt"] for ticket in body] == sorted(
        [first["createdAt"], second["createdAt"]],
        reverse=True,
    )
    assert body[0]["ticketNumber"] == second["ticketNumber"]
    assert "trackingCode" not in body[0]
    assert "imageReferences" not in body[0]
    assert "imageObjectKey" not in body[0]
    assert body[0]["department"] == {
        "departmentId": "d1111111-1111-1111-1111-111111111111",
        "name": "Road Maintenance",
    }
    assert body[0]["departmentId"] == "d1111111-1111-1111-1111-111111111111"
    assert body[0]["municipalityId"] is None
    assert set(body[0]["location"]) == {"latitude", "longitude", "addressText"}
    assert body[0]["location"]["latitude"] == VALID_PAYLOAD["location"]["latitude"]
    assert body[0]["location"]["longitude"] == VALID_PAYLOAD["location"]["longitude"]
    assert body[0]["location"]["addressText"] == VALID_PAYLOAD["location"]["addressText"]
    assert body[1]["ticketNumber"] == first["ticketNumber"]


def test_list_tickets_returns_empty_list_when_no_tickets_exist(client):
    response = client.get("/v1/tickets")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_get_ticket_returns_ticket_by_id(client):
    created = create_ticket(client)

    response = client.get(f"/v1/tickets/{created['ticketId']}")

    assert response.status_code == 200
    body = response.json()
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert body["ticketId"] == created["ticketId"]
    assert body["ticketNumber"] == created["ticketNumber"]
    assert body["trackingCode"] == created["trackingCode"]
    assert body["description"] == stored.description
    assert body["contact"] == stored.contact.model_dump(by_alias=True)
    assert body["location"] == stored.location.model_dump(by_alias=True)
    assert body["imageReferences"][0]["objectKey"] == stored.image_object_key
    image_url = body["imageReferences"][0]["url"]
    assert image_url is None or image_url.startswith("https://")
    assert body["imageObjectKey"] == stored.image_object_key
    assert body["status"] == "SUBMITTED"
    assert body["category"] == "PENDING_CLASSIFICATION"
    assert body["priority"] == stored.priority
    assert body["ai"]["urgencyScore"] == stored.urgency_score
    assert body["ai"]["urgencyReason"] == stored.urgency_reason
    assert body["department"] == {
        "departmentId": "d1111111-1111-1111-1111-111111111111",
        "name": "Road Maintenance",
    }
    assert body["departmentId"] == "d1111111-1111-1111-1111-111111111111"
    assert body["createdBy"] == stored.created_by
    assert body["municipalityId"] == stored.municipality_id
    assert body["duplicateGroupId"] == stored.duplicate_group_id
    assert body["createdAt"] == created["createdAt"]
    # AI processing runs after create and refreshes updatedAt.
    assert body["updatedAt"] is not None
    assert body["updatedAt"] >= created["createdAt"]
    assert body["ai"]["aiProcessingStatus"] == "completed"


def test_get_ticket_returns_duplicate_suggestions(client):
    main = create_ticket(client, "Overflowing garbage bins near Hamra Street.")
    duplicate = create_ticket(client, "Garbage bags are piling up beside the same sidewalk.")
    unrelated = create_ticket(client, "Broken street light on a far road.")
    grouped = create_ticket(client, "More waste bags beside the same sidewalk.")

    ticket_store.patch_fields(
        main["ticketId"],
        {
            "ai_suggested_category": "waste",
        },
    )
    ticket_store.patch_fields(
        duplicate["ticketId"],
        {
            "ai_suggested_category": "waste",
            "status": "IN_PROGRESS",
        },
    )
    ticket_store.patch_fields(
        unrelated["ticketId"],
        {
            "category": "street_lighting",
            "ai_suggested_category": "street_lighting",
        },
    )
    ticket_store.patch_fields(
        grouped["ticketId"],
        {
            "ai_suggested_category": "waste",
            "duplicate_group_id": "dup_existing",
        },
    )

    response = client.get(f"/v1/tickets/{main['ticketId']}")

    assert response.status_code == 200
    suggestions = response.json()["duplicateSuggestions"]
    assert len(suggestions) == 1
    assert suggestions[0]["ticketId"] == duplicate["ticketId"]
    assert suggestions[0]["ticketNumber"] == duplicate["ticketNumber"]
    assert suggestions[0]["distanceMeters"] >= 0
    assert suggestions[0]["status"] == "IN_PROGRESS"
    assert suggestions[0]["category"] == "waste"
    assert suggestions[0]["ticketId"] != grouped["ticketId"]


def test_get_ticket_returns_empty_duplicate_suggestions_when_none_exist(client):
    created = create_ticket(client, "Broken street light near the promenade.")

    response = client.get(f"/v1/tickets/{created['ticketId']}")

    assert response.status_code == 200
    assert response.json()["duplicateSuggestions"] == []


def test_get_ticket_returns_404_for_unknown_ticket(client):
    response = client.get("/v1/tickets/tkt_missing")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "TICKET_NOT_FOUND"
    assert body["error"]["message"] == "Ticket was not found."
    assert body["error"]["requestId"].startswith("req_")
    assert "X-Request-Id" in response.headers


def test_update_ticket_status_returns_updated_ticket(client):
    created = create_ticket(client)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "UNDER_REVIEW"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ticketId"] == created["ticketId"]
    assert body["status"] == "UNDER_REVIEW"
    assert body["updatedAt"]
    assert len(body["statusHistory"]) == 2

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.status == "UNDER_REVIEW"
    assert stored.updated_at == body["updatedAt"]


def test_update_ticket_status_returns_404_for_unknown_ticket(client):
    response = client.patch("/v1/tickets/tkt_missing/status", json={"status": "IN_PROGRESS"})

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "TICKET_NOT_FOUND"
    assert body["error"]["message"] == "Ticket was not found."
    assert body["error"]["requestId"].startswith("req_")
    assert "X-Request-Id" in response.headers


def test_update_ticket_status_rejects_invalid_status(client):
    created = create_ticket(client)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "ARCHIVED"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
