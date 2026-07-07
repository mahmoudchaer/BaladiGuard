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
    assert [ticket["ticketId"] for ticket in body] == [first["ticketId"], second["ticketId"]]
    assert body[0]["ticketNumber"] == first["ticketNumber"]
    assert body[0]["trackingCode"] == first["trackingCode"]
    assert body[0]["imageReferences"][0]["objectKey"] == VALID_PAYLOAD["imageObjectKey"]
    assert body[0]["imageReferences"][0]["contentType"] is None
    assert body[0]["imageReferences"][0]["createdAt"] is None
    assert body[0]["imageObjectKey"] == VALID_PAYLOAD["imageObjectKey"]
    assert body[0]["department"] is None
    assert body[0]["departmentId"] is None
    assert body[1]["ticketNumber"] == second["ticketNumber"]


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
    assert body["createdAt"] == created["createdAt"]
    assert body["updatedAt"] == created["createdAt"]


def test_get_ticket_returns_404_for_unknown_ticket(client):
    response = client.get("/v1/tickets/tkt_missing")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "TICKET_NOT_FOUND"
    assert body["error"]["message"] == "Ticket was not found."
    assert body["error"]["requestId"].startswith("req_")
    assert "X-Request-Id" in response.headers
