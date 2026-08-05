from app.database.memory import ticket_store
from app.schemas.citizen import CitizenProfileUpdateRequest
from app.services.citizens.service import citizen_service
from tests.conftest import (
    contribution_ready_auth_headers,
    ensure_contribution_ready_citizen,
)
from tests.test_submit_ticket import VALID_PAYLOAD

PUBLIC_FORBIDDEN_FIELDS = {
    "ticketId",
    "trackingCode",
    "ownerUserId",
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


def _submit_public_report(
    anonymous_client,
    *,
    phone: str = "+96170123456",
    full_name: str = "Citizen Name",
    public_name_visible: bool = False,
    description: str = VALID_PAYLOAD["description"],
) -> dict:
    user, _token = ensure_contribution_ready_citizen(
        phone=phone,
        full_name=full_name,
        email=None,
    )
    if public_name_visible:
        citizen_service.update_profile(
            user.user_id,
            CitizenProfileUpdateRequest(publicNameVisible=True),
        )

    response = anonymous_client.post(
        "/v1/tickets",
        json={**VALID_PAYLOAD, "description": description},
        headers=contribution_ready_auth_headers(
            phone=phone,
            full_name=full_name,
            email=None,
        ),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_public_ticket_feed_is_guest_readable_and_privacy_safe(anonymous_client):
    created = _submit_public_report(
        anonymous_client,
        phone="+96170111111",
        full_name="Private Reporter",
        public_name_visible=False,
    )

    response = anonymous_client.get("/v1/tickets/public")

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 20
    assert body["nextCursor"] is None
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["ticketNumber"] == created["ticketNumber"]
    assert item["status"] == "SUBMITTED"
    assert item["category"] is None
    assert item["location"] == {"addressText": VALID_PAYLOAD["location"]["addressText"]}
    assert item["mapLocation"] == {
        "addressText": VALID_PAYLOAD["location"]["addressText"],
        "latitude": 33.896,
        "longitude": 35.478,
    }
    assert item["attribution"] == {"displayName": "Community member", "isNamed": False}
    assert PUBLIC_FORBIDDEN_FIELDS.isdisjoint(item)
    assert "Private Reporter" not in str(item)
    assert "+96170111111" not in str(item)
    assert created["trackingCode"] not in str(item)


def test_public_ticket_detail_uses_ticket_number_and_name_opt_in(anonymous_client):
    created = _submit_public_report(
        anonymous_client,
        phone="+96170222222",
        full_name="Ada Public",
        public_name_visible=True,
    )

    response = anonymous_client.get(f"/v1/tickets/public/{created['ticketNumber'].lower()}")

    assert response.status_code == 200
    body = response.json()
    assert body["ticketNumber"] == created["ticketNumber"]
    assert body["attribution"] == {"displayName": "Ada Public", "isNamed": True}
    assert PUBLIC_FORBIDDEN_FIELDS.isdisjoint(body)
    assert "+96170222222" not in str(body)


def test_public_ticket_feed_is_bounded_and_cursor_paginated(anonymous_client):
    first = _submit_public_report(
        anonymous_client,
        phone="+96170333333",
        description="First public road report near the university gate.",
    )
    second = _submit_public_report(
        anonymous_client,
        phone="+96170444444",
        description="Second public road report near the university gate.",
    )

    first_page = anonymous_client.get("/v1/tickets/public", params={"limit": 1})

    assert first_page.status_code == 200
    first_body = first_page.json()
    assert first_body["limit"] == 1
    assert [item["ticketNumber"] for item in first_body["items"]] == [second["ticketNumber"]]
    assert first_body["nextCursor"] is not None

    second_page = anonymous_client.get(
        "/v1/tickets/public",
        params={"limit": 1, "cursor": first_body["nextCursor"]},
    )

    assert second_page.status_code == 200
    assert [item["ticketNumber"] for item in second_page.json()["items"]] == [first["ticketNumber"]]


def test_public_ticket_detail_returns_404_without_leaking_internal_id(anonymous_client):
    response = anonymous_client.get("/v1/tickets/public/BG-2099-9999")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "TICKET_NOT_FOUND"
    assert "tkt_" not in str(body)


def test_public_ticket_feed_rejects_invalid_cursor(anonymous_client):
    response = anonymous_client.get("/v1/tickets/public", params={"cursor": "not-a-cursor"})

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == "cursor" for detail in body["error"]["details"])


def test_public_feed_hides_legacy_ownerless_attribution(anonymous_client):
    created = _submit_public_report(anonymous_client)
    ticket_store.patch_fields(created["ticketId"], {"owner_user_id": None})

    response = anonymous_client.get("/v1/tickets/public")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["attribution"] == {"displayName": "Community member", "isNamed": False}
