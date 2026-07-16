from app.database.memory import ticket_store
from tests.test_submit_ticket import VALID_PAYLOAD


def create_ticket(client, description: str = VALID_PAYLOAD["description"]) -> dict:
    payload = {**VALID_PAYLOAD, "description": description}
    response = client.post("/v1/tickets", json=payload)
    assert response.status_code == 201
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
    body = response.json()
    assert [ticket["ticketId"] for ticket in body] == [second["ticketId"], first["ticketId"]]
    assert [ticket["createdAt"] for ticket in body] == sorted(
        [first["createdAt"], second["createdAt"]],
        reverse=True,
    )
    assert body[0]["ticketNumber"] == second["ticketNumber"]
    assert body[0]["trackingCode"] == second["trackingCode"]
    assert body[0]["imageReferences"][0]["objectKey"] == VALID_PAYLOAD["imageObjectKey"]
    assert body[0]["imageReferences"][0]["contentType"] is None
    assert body[0]["imageReferences"][0]["createdAt"] is None
    assert body[0]["imageObjectKey"] == VALID_PAYLOAD["imageObjectKey"]
    assert body[0]["department"] is None
    assert body[0]["departmentId"] is None
    assert body[0]["createdBy"] is None
    assert body[0]["municipalityId"] is None
    assert body[0]["duplicateGroupId"] is None
    assert body[1]["ticketNumber"] == first["ticketNumber"]


def test_list_tickets_returns_empty_list_when_no_tickets_exist(client):
    response = client.get("/v1/tickets")

    assert response.status_code == 200
    assert response.json() == []


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
    assert body["priority"] is None
    assert body["department"] is None
    assert body["departmentId"] is None
    assert body["createdBy"] == stored.created_by
    assert body["municipalityId"] == stored.municipality_id
    assert body["duplicateGroupId"] == stored.duplicate_group_id
    assert body["createdAt"] == created["createdAt"]
    # AI processing runs after create and refreshes updatedAt.
    assert body["updatedAt"] is not None
    assert body["updatedAt"] >= created["createdAt"]
    assert body["ai"]["aiProcessingStatus"] == "completed"


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
