from app.database.memory import ticket_store
from app.schemas.stored_ticket import PENDING_CLASSIFICATION

VALID_PAYLOAD = {
    "description": "Large pothole reported near the university gate causing traffic disruption.",
    "languageHint": "auto",
    "contact": {
        "name": "Citizen Name",
        "phone": "+96170123456",
        "email": "citizen@example.com",
        "preferredChannel": "SMS",
    },
    "location": {
        "latitude": 33.896112,
        "longitude": 35.478419,
        "addressText": "Near AUB Main Gate, Hamra, Beirut",
        "source": "GPS",
    },
    "imageObjectKey": "reports/temp/01JZABCDEF/photo.jpg",
    "clientMetadata": {
        "platform": "ios",
        "appVersion": "0.1.0",
    },
}


def test_submit_ticket_success(client):
    response = client.post("/v1/tickets", json=VALID_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["ticketId"].startswith("tkt_")
    assert body["ticketNumber"].startswith("BG-")
    assert len(body["trackingCode"]) == 6
    assert body["status"] == "SUBMITTED"
    assert body["message"] == "Your report was submitted successfully."
    assert body["createdAt"].endswith("Z")
    assert "X-Request-Id" in response.headers

    stored = ticket_store.get(body["ticketId"])
    assert stored is not None
    assert stored.description == VALID_PAYLOAD["description"]
    assert stored.contact.name == VALID_PAYLOAD["contact"]["name"]
    assert stored.contact.phone == VALID_PAYLOAD["contact"]["phone"]
    assert stored.contact.email == VALID_PAYLOAD["contact"]["email"]
    assert stored.location.latitude == VALID_PAYLOAD["location"]["latitude"]
    assert stored.location.longitude == VALID_PAYLOAD["location"]["longitude"]
    assert stored.location.address_text == VALID_PAYLOAD["location"]["addressText"]
    assert stored.location.source == VALID_PAYLOAD["location"]["source"]
    assert stored.image_object_key == VALID_PAYLOAD["imageObjectKey"]
    assert stored.ticket_number == body["ticketNumber"]
    assert stored.tracking_code == body["trackingCode"]
    assert stored.status == "SUBMITTED"
    assert stored.category == PENDING_CLASSIFICATION
    assert stored.created_at == body["createdAt"]
    assert stored.updated_at == body["createdAt"]


def test_submit_ticket_requires_contact_channel(client):
    payload = {
        **VALID_PAYLOAD,
        "contact": {
            "name": "Citizen Name",
        },
    }

    response = client.post("/v1/tickets", json=payload)

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == "contact" for detail in body["error"]["details"])


def test_submit_ticket_rejects_short_description(client):
    payload = {
        **VALID_PAYLOAD,
        "description": "short",
    }

    response = client.post("/v1/tickets", json=payload)

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == "description" for detail in body["error"]["details"])


def test_submit_ticket_rejects_invalid_coordinates(client):
    payload = {
        **VALID_PAYLOAD,
        "location": {
            **VALID_PAYLOAD["location"],
            "latitude": 120,
        },
    }

    response = client.post("/v1/tickets", json=payload)

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any("latitude" in detail["field"] for detail in body["error"]["details"])


def test_submit_ticket_requires_image_reference(client):
    payload = {
        **VALID_PAYLOAD,
        "imageObjectKey": "   ",
    }

    response = client.post("/v1/tickets", json=payload)

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == "imageObjectKey" for detail in body["error"]["details"])
