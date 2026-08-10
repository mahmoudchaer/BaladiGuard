import math

import pytest
from pydantic import ValidationError

from app.database.memory import ticket_store
from app.schemas.stored_ticket import PENDING_CLASSIFICATION
from app.schemas.ticket import ReportLocation
from app.services.ai_job_queue import ai_job_queue
from tests.conftest import (
    DEFAULT_CITIZEN_EMAIL,
    DEFAULT_CITIZEN_FULL_NAME,
    DEFAULT_CITIZEN_PHONE,
    ensure_contribution_ready_citizen,
)

# Contact is server-snapshotted from the authenticated profile; clients omit it.
VALID_PAYLOAD = {
    "description": "Large pothole reported near the university gate causing traffic disruption.",
    "languageHint": "auto",
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

EXPECTED_CONTACT = {
    "name": DEFAULT_CITIZEN_FULL_NAME,
    "phone": DEFAULT_CITIZEN_PHONE,
    "email": DEFAULT_CITIZEN_EMAIL,
    "preferredChannel": "SMS",
}


def test_submit_ticket_success(client, contribution_ready_citizen_headers):
    user, _token = ensure_contribution_ready_citizen()
    response = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=contribution_ready_citizen_headers,
    )

    assert response.status_code == 201
    assert ai_job_queue.run_once().outcome == "succeeded"
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
    assert stored.owner_user_id == user.user_id
    assert stored.contact.name == EXPECTED_CONTACT["name"]
    assert stored.contact.phone == EXPECTED_CONTACT["phone"]
    assert stored.contact.email == EXPECTED_CONTACT["email"]
    assert stored.contact.preferred_channel == EXPECTED_CONTACT["preferredChannel"]
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
    # AI processing runs after create and refreshes updatedAt.
    assert stored.updated_at is not None
    assert stored.updated_at >= body["createdAt"]
    assert stored.ai_processing_status == "completed"


def test_submit_ticket_rejects_client_contact(client, contribution_ready_citizen_headers):
    payload = {
        **VALID_PAYLOAD,
        "contact": {
            "name": "Spoofed Name",
            "phone": "+96171999999",
            "email": "spoof@example.com",
            "preferredChannel": "EMAIL",
        },
    }

    response = client.post(
        "/v1/tickets",
        json=payload,
        headers=contribution_ready_citizen_headers,
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any("contact" in detail["message"].lower() for detail in body["error"]["details"])


def test_submit_ticket_rejects_client_owner_user_id(client, contribution_ready_citizen_headers):
    payload = {**VALID_PAYLOAD, "ownerUserId": "usr_spoofed_owner"}

    response = client.post(
        "/v1/tickets",
        json=payload,
        headers=contribution_ready_citizen_headers,
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any("owneruserid" in detail["message"].lower() for detail in body["error"]["details"])


def test_submit_ticket_rejects_short_description(client, contribution_ready_citizen_headers):
    payload = {
        **VALID_PAYLOAD,
        "description": "short",
    }

    response = client.post(
        "/v1/tickets",
        json=payload,
        headers=contribution_ready_citizen_headers,
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == "description" for detail in body["error"]["details"])


def test_submit_ticket_rejects_invalid_coordinates(client, contribution_ready_citizen_headers):
    payload = {
        **VALID_PAYLOAD,
        "location": {
            **VALID_PAYLOAD["location"],
            "latitude": 120,
        },
    }

    response = client.post(
        "/v1/tickets",
        json=payload,
        headers=contribution_ready_citizen_headers,
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any("latitude" in detail["field"] for detail in body["error"]["details"])


@pytest.mark.parametrize("invalid_latitude", ["33.896112", True, None])
def test_submit_ticket_rejects_non_numeric_coordinates(
    client,
    contribution_ready_citizen_headers,
    invalid_latitude,
):
    payload = {
        **VALID_PAYLOAD,
        "location": {
            **VALID_PAYLOAD["location"],
            "latitude": invalid_latitude,
        },
    }

    response = client.post(
        "/v1/tickets",
        json=payload,
        headers=contribution_ready_citizen_headers,
    )

    assert response.status_code == 400
    assert any(
        detail["field"] == "location.latitude" for detail in response.json()["error"]["details"]
    )


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (-90, -180),
        (90, 180),
        (0, 0),
    ],
)
def test_submit_ticket_accepts_coordinate_boundaries(
    client,
    contribution_ready_citizen_headers,
    latitude,
    longitude,
):
    payload = {
        **VALID_PAYLOAD,
        "location": {
            **VALID_PAYLOAD["location"],
            "latitude": latitude,
            "longitude": longitude,
        },
    }

    response = client.post(
        "/v1/tickets",
        json=payload,
        headers=contribution_ready_citizen_headers,
    )

    assert response.status_code == 201
    stored = ticket_store.get(response.json()["ticketId"])
    assert stored is not None
    assert stored.location.latitude == latitude
    assert stored.location.longitude == longitude


@pytest.mark.parametrize("invalid_coordinate", [math.nan, math.inf, -math.inf])
def test_report_location_rejects_non_finite_coordinates(invalid_coordinate):
    with pytest.raises(ValidationError, match="finite number"):
        ReportLocation(
            latitude=invalid_coordinate,
            longitude=35.478419,
            addressText="Hamra, Beirut",
            source="GPS",
        )


def test_submit_ticket_trims_readable_address(client, contribution_ready_citizen_headers):
    payload = {
        **VALID_PAYLOAD,
        "location": {
            **VALID_PAYLOAD["location"],
            "addressText": "  Near AUB Main Gate, Hamra, Beirut  ",
        },
    }

    response = client.post(
        "/v1/tickets",
        json=payload,
        headers=contribution_ready_citizen_headers,
    )

    assert response.status_code == 201
    stored = ticket_store.get(response.json()["ticketId"])
    assert stored is not None
    assert stored.location.address_text == "Near AUB Main Gate, Hamra, Beirut"


def test_submit_ticket_rejects_blank_address(client, contribution_ready_citizen_headers):
    payload = {
        **VALID_PAYLOAD,
        "location": {
            **VALID_PAYLOAD["location"],
            "addressText": "   ",
        },
    }

    response = client.post(
        "/v1/tickets",
        json=payload,
        headers=contribution_ready_citizen_headers,
    )

    assert response.status_code == 400
    assert any(
        detail["field"] == "location.addressText" for detail in response.json()["error"]["details"]
    )


def test_submit_ticket_requires_image_reference(client, contribution_ready_citizen_headers):
    payload = {
        **VALID_PAYLOAD,
        "imageObjectKey": "   ",
    }

    response = client.post(
        "/v1/tickets",
        json=payload,
        headers=contribution_ready_citizen_headers,
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == "imageObjectKey" for detail in body["error"]["details"])


def test_guest_submit_requires_authentication(anonymous_client):
    response = anonymous_client.post("/v1/tickets", json=VALID_PAYLOAD)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.headers.get("WWW-Authenticate", "").startswith("Bearer")


def test_incomplete_citizen_submit_requires_contribution_profile(anonymous_client):
    from app.services.citizens.service import citizen_service

    user = citizen_service.create_citizen(phone="+96170111111")
    token = citizen_service.issue_session(user.user_id)

    response = anonymous_client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONTRIBUTION_PROFILE_REQUIRED"


def test_inactive_citizen_session_rejected_on_submit(anonymous_client):
    from app.database.memory_citizen import citizen_store

    user, token = ensure_contribution_ready_citizen(phone="+96170222222")
    citizen_store.update(user.model_copy(update={"active": False}))

    response = anonymous_client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_contact_snapshot_immutable_after_profile_edit(
    client,
    contribution_ready_citizen_headers,
):
    from app.schemas.citizen import CitizenProfileUpdateRequest
    from app.services.citizens.service import citizen_service

    user, _token = ensure_contribution_ready_citizen()
    response = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=contribution_ready_citizen_headers,
    )
    assert response.status_code == 201
    ticket_id = response.json()["ticketId"]

    citizen_service.update_profile(
        user.user_id,
        CitizenProfileUpdateRequest.model_validate(
            {
                "fullName": "Updated Name",
                "email": "updated@example.com",
                "notificationPreferences": {"ticketUpdates": "EMAIL"},
            }
        ),
    )

    stored = ticket_store.get(ticket_id)
    assert stored is not None
    assert stored.owner_user_id == user.user_id
    assert stored.contact.name == EXPECTED_CONTACT["name"]
    assert stored.contact.phone == EXPECTED_CONTACT["phone"]
    assert stored.contact.email == EXPECTED_CONTACT["email"]
    assert stored.contact.preferred_channel == "SMS"


def test_staff_detail_includes_owner_user_id(client, contribution_ready_citizen_headers):
    user, _token = ensure_contribution_ready_citizen()
    created = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=contribution_ready_citizen_headers,
    ).json()

    detail = client.get(f"/v1/tickets/{created['ticketId']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["ownerUserId"] == user.user_id
    assert body["contact"]["phone"] == EXPECTED_CONTACT["phone"]


def test_public_track_hides_owner_and_contact(client, contribution_ready_citizen_headers):
    created = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=contribution_ready_citizen_headers,
    ).json()

    track = client.get(f"/v1/tickets/track/{created['trackingCode']}")
    assert track.status_code == 200
    body = track.json()
    assert "ownerUserId" not in body
    assert "contact" not in body
    assert EXPECTED_CONTACT["phone"] not in str(body)
