from app.core.rate_limit import public_ticket_rate_limiter
from app.database.memory import ticket_store
from app.database.store_factory import get_citizen_store
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


def _publish_report(
    created: dict,
    *,
    category: str = "road_damage",
    description: str = "Staff-approved public summary of the road hazard.",
    location_label: str = "Hamra, Beirut",
    published_at: str = "2026-08-05T12:00:00Z",
) -> None:
    patched = ticket_store.patch_fields(
        created["ticketId"],
        {
            "final_category": category,
            "category": category,
            "public_status": "PUBLISHED",
            "public_description": description,
            "public_location_label": location_label,
            "public_published_at": published_at,
            "updated_at": published_at,
        },
    )
    assert patched is not None


def test_public_ticket_feed_is_guest_readable_and_privacy_safe(anonymous_client):
    created = _submit_public_report(
        anonymous_client,
        phone="+96170111111",
        full_name="Private Reporter",
        public_name_visible=False,
    )
    _publish_report(created)

    response = anonymous_client.get("/v1/tickets/public")

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 20
    assert body["nextCursor"] is None
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["ticketNumber"] == created["ticketNumber"]
    assert item["status"] == "SUBMITTED"
    assert item["category"] == "road_damage"
    assert item["description"] == "Staff-approved public summary of the road hazard."
    assert item["location"] == {"addressText": "Hamra, Beirut"}
    assert item["mapLocation"] == {
        "addressText": "Hamra, Beirut",
        "latitude": 33.896,
        "longitude": 35.478,
    }
    assert item["attribution"] == {"displayName": "Community member", "isNamed": False}
    assert "photoUrl" in item
    # Unapproved uploads stay private even when imageObjectKey exists on the ticket.
    assert item["photoUrl"] is None
    assert PUBLIC_FORBIDDEN_FIELDS.isdisjoint(item)
    assert "Private Reporter" not in str(item)
    assert "+96170111111" not in str(item)
    assert created["trackingCode"] not in str(item)
    assert VALID_PAYLOAD["location"]["addressText"] not in str(item)


def test_public_ticket_detail_uses_ticket_number_and_name_opt_in(anonymous_client):
    created = _submit_public_report(
        anonymous_client,
        phone="+96170222222",
        full_name="Ada Public",
        public_name_visible=True,
    )
    _publish_report(created, location_label="Ras Beirut")

    response = anonymous_client.get(f"/v1/tickets/public/{created['ticketNumber'].lower()}")

    assert response.status_code == 200
    body = response.json()
    assert body["ticketNumber"] == created["ticketNumber"]
    assert body["attribution"] == {"displayName": "Ada Public", "isNamed": True}
    assert body["location"] == {"addressText": "Ras Beirut"}
    assert PUBLIC_FORBIDDEN_FIELDS.isdisjoint(body)
    assert "+96170222222" not in str(body)
    assert VALID_PAYLOAD["location"]["addressText"] not in str(body)


def test_public_ticket_feed_excludes_unreviewed_and_unapproved_reports(anonymous_client):
    unreviewed = _submit_public_report(anonymous_client, phone="+96170233333")
    incomplete = _submit_public_report(anonymous_client, phone="+96170233334")
    ticket_store.patch_fields(
        incomplete["ticketId"],
        {
            "final_category": "road_damage",
            "category": "road_damage",
            "public_status": "PUBLISHED",
            "public_location_label": "Hamra, Beirut",
        },
    )

    response = anonymous_client.get("/v1/tickets/public")

    assert response.status_code == 200
    assert response.json()["items"] == []

    detail = anonymous_client.get(f"/v1/tickets/public/{unreviewed['ticketNumber']}")
    assert detail.status_code == 404


def test_public_ticket_does_not_publish_cleaned_description_or_embedded_pii(anonymous_client):
    created = _submit_public_report(
        anonymous_client,
        phone="+96170233335",
        description="My phone is +96170123456 and Samir accused the shop at Bliss Street.",
    )
    ticket_store.patch_fields(
        created["ticketId"],
        {
            "cleaned_description": "My phone is +96170123456 and Samir accused the shop.",
        },
    )
    _publish_report(
        created,
        description="Road hazard reported in the area; details reviewed by staff.",
        location_label="Hamra, Beirut",
    )

    response = anonymous_client.get(f"/v1/tickets/public/{created['ticketNumber']}")

    assert response.status_code == 200
    body_text = str(response.json())
    assert "+96170123456" not in body_text
    assert "Samir" not in body_text
    assert "Bliss Street" not in body_text


def test_public_ticket_feed_is_bounded_and_cursor_paginated(anonymous_client):
    first = _submit_public_report(
        anonymous_client,
        phone="+96170333333",
        description="First public road report near the university gate.",
    )
    _publish_report(first, published_at="2026-08-05T12:00:00Z")
    second = _submit_public_report(
        anonymous_client,
        phone="+96170444444",
        description="Second public road report near the university gate.",
    )
    _publish_report(second, published_at="2026-08-05T13:00:00Z")

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


def test_public_ticket_pagination_stays_stable_when_new_report_is_published(anonymous_client):
    first = _submit_public_report(anonymous_client, phone="+96170555551")
    _publish_report(first, published_at="2026-08-05T12:00:00Z")
    second = _submit_public_report(anonymous_client, phone="+96170555552")
    _publish_report(second, published_at="2026-08-05T13:00:00Z")
    first_page = anonymous_client.get("/v1/tickets/public", params={"limit": 1})
    assert first_page.status_code == 200
    assert [item["ticketNumber"] for item in first_page.json()["items"]] == [second["ticketNumber"]]

    newer = _submit_public_report(anonymous_client, phone="+96170555553")
    _publish_report(newer, published_at="2026-08-05T14:00:00Z")
    second_page = anonymous_client.get(
        "/v1/tickets/public",
        params={"limit": 1, "cursor": first_page.json()["nextCursor"]},
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
    _publish_report(created)
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    ticket_store.save(stored.model_copy(update={"owner_user_id": None}))

    response = anonymous_client.get("/v1/tickets/public")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["attribution"] == {"displayName": "Community member", "isNamed": False}


def test_public_attribution_reflects_profile_visibility_and_inactive_accounts(anonymous_client):
    created = _submit_public_report(
        anonymous_client,
        phone="+96170666666",
        full_name="Visible Citizen",
        public_name_visible=True,
    )
    _publish_report(created)

    detail = anonymous_client.get(f"/v1/tickets/public/{created['ticketNumber']}")
    assert detail.status_code == 200
    assert detail.json()["attribution"] == {"displayName": "Visible Citizen", "isNamed": True}

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None and stored.owner_user_id is not None
    citizen_service.update_profile(
        stored.owner_user_id,
        CitizenProfileUpdateRequest(publicNameVisible=False),
    )
    hidden = anonymous_client.get(f"/v1/tickets/public/{created['ticketNumber']}")
    assert hidden.status_code == 200
    assert hidden.json()["attribution"] == {"displayName": "Community member", "isNamed": False}

    citizen_service.update_profile(
        stored.owner_user_id,
        CitizenProfileUpdateRequest(publicNameVisible=True),
    )
    citizen_store = get_citizen_store()
    user = citizen_store.get(stored.owner_user_id)
    assert user is not None
    citizen_store.update(user.model_copy(update={"active": False}))
    public_ticket_rate_limiter.reset()
    inactive = anonymous_client.get(f"/v1/tickets/public/{created['ticketNumber']}")
    assert inactive.status_code == 200
    assert inactive.json()["attribution"] == {"displayName": "Community member", "isNamed": False}


def test_public_ticket_photo_requires_staff_approved_public_image_key(
    anonymous_client, monkeypatch
):
    created = _submit_public_report(anonymous_client, phone="+96170777777")
    _publish_report(created)
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    raw_upload_key = stored.image_object_key

    # Raw upload key alone must never become a public photo.
    without_approval = anonymous_client.get(f"/v1/tickets/public/{created['ticketNumber']}")
    assert without_approval.status_code == 200
    assert without_approval.json()["photoUrl"] is None
    assert raw_upload_key not in without_approval.text

    monkeypatch.setattr(
        "app.services.complaints.ticket_read_mapper.build_image_url",
        lambda key: f"https://example.test/signed/{key}",
    )
    from app.services.uploads.photo_upload_service import PhotoUploadService

    approved_key = (
        f"reports/redacted/v1/{PhotoUploadService.ticket_scope(created['ticketId'])}/"
        "g1/approved.jpg"
    )
    patched = ticket_store.patch_fields(
        created["ticketId"],
        {"public_image_object_key": approved_key},
    )
    assert patched is not None

    with_approval = anonymous_client.get(f"/v1/tickets/public/{created['ticketNumber']}")
    assert with_approval.status_code == 200
    body = with_approval.json()
    assert body["photoUrl"] == f"https://example.test/signed/{approved_key}"
    assert "imageObjectKey" not in body
    assert raw_upload_key not in with_approval.text
