"""Staff public content / photo approval tests."""

from __future__ import annotations

from app.database.memory import ticket_store
from tests.conftest import (
    contribution_ready_auth_headers,
    ensure_contribution_ready_citizen,
    issue_test_staff_token,
)
from tests.test_submit_ticket import VALID_PAYLOAD


def _submit_report(client, *, phone: str = "+96170888888") -> dict:
    ensure_contribution_ready_citizen(phone=phone, full_name="Public Photo Citizen", email=None)
    response = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=contribution_ready_auth_headers(
            phone=phone,
            full_name="Public Photo Citizen",
            email=None,
        ),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _review_category(client, ticket_id: str, token: str) -> None:
    response = client.patch(
        f"/v1/tickets/{ticket_id}/category",
        json={"finalCategory": "road_damage"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text


def test_staff_can_publish_with_approved_original_photo(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.complaints.ticket_read_mapper.build_image_url",
        lambda key: f"https://example.test/{key}",
    )
    created = _submit_report(client)
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    raw_key = stored.image_object_key
    token = issue_test_staff_token(client)
    _review_category(client, created["ticketId"], token)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/public",
        json={
            "publicStatus": "PUBLISHED",
            "publicDescription": "Staff-approved road hazard near campus.",
            "publicLocationLabel": "Hamra, Beirut",
            "approveOriginalPhoto": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["public"]["status"] == "PUBLISHED"
    assert body["public"]["imageObjectKey"] == raw_key
    assert any(
        entry["actionType"] == "PUBLIC_CONTENT_UPDATE" for entry in body.get("auditHistory", [])
    )

    public = client.get(f"/v1/tickets/public/{created['ticketNumber']}")
    assert public.status_code == 200
    public_body = public.json()
    assert public_body["photoUrl"] == f"https://example.test/{raw_key}"
    assert "imageObjectKey" not in public_body


def test_staff_publish_without_photo_keeps_photo_null(client):
    created = _submit_report(client, phone="+96170888889")
    token = issue_test_staff_token(client)
    _review_category(client, created["ticketId"], token)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/public",
        json={
            "publicStatus": "PUBLISHED",
            "publicDescription": "Approved summary without a public photo.",
            "publicLocationLabel": "Ras Beirut",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["public"]["imageObjectKey"] is None

    public = client.get(f"/v1/tickets/public/{created['ticketNumber']}")
    assert public.status_code == 200
    assert public.json()["photoUrl"] is None


def test_staff_can_clear_public_photo(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.complaints.ticket_read_mapper.build_image_url",
        lambda key: f"https://example.test/{key}",
    )
    created = _submit_report(client, phone="+96170888890")
    token = issue_test_staff_token(client)
    _review_category(client, created["ticketId"], token)

    approved = client.patch(
        f"/v1/tickets/{created['ticketId']}/public",
        json={
            "publicStatus": "PUBLISHED",
            "publicDescription": "Hazard with temporary public photo.",
            "publicLocationLabel": "Hamra",
            "approveOriginalPhoto": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert approved.status_code == 200

    cleared = client.patch(
        f"/v1/tickets/{created['ticketId']}/public",
        json={
            "publicStatus": "PUBLISHED",
            "publicDescription": "Hazard with temporary public photo.",
            "publicLocationLabel": "Hamra",
            "clearPublicPhoto": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["public"]["imageObjectKey"] is None
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.public_image_object_key is None


def test_publish_requires_final_category_and_public_text(client):
    created = _submit_report(client, phone="+96170888891")
    token = issue_test_staff_token(client)

    missing_category = client.patch(
        f"/v1/tickets/{created['ticketId']}/public",
        json={
            "publicStatus": "PUBLISHED",
            "publicDescription": "Missing category still.",
            "publicLocationLabel": "Hamra",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing_category.status_code == 400
    assert missing_category.json()["error"]["code"] == "VALIDATION_ERROR"

    _review_category(client, created["ticketId"], token)
    missing_text = client.patch(
        f"/v1/tickets/{created['ticketId']}/public",
        json={
            "publicStatus": "PUBLISHED",
            "publicDescription": "   ",
            "publicLocationLabel": "Hamra",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing_text.status_code == 400


def test_public_content_update_requires_staff_auth(anonymous_client):
    created = _submit_report(anonymous_client, phone="+96170888892")
    response = anonymous_client.patch(
        f"/v1/tickets/{created['ticketId']}/public",
        json={
            "publicStatus": "PUBLISHED",
            "publicDescription": "Nope",
            "publicLocationLabel": "Hamra",
        },
    )
    assert response.status_code == 401


def test_unpublish_removes_ticket_from_public_feed(client):
    created = _submit_report(client, phone="+96170888893")
    token = issue_test_staff_token(client)
    _review_category(client, created["ticketId"], token)

    published = client.patch(
        f"/v1/tickets/{created['ticketId']}/public",
        json={
            "publicStatus": "PUBLISHED",
            "publicDescription": "Published briefly.",
            "publicLocationLabel": "Hamra",
            "approveOriginalPhoto": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert published.status_code == 200
    assert client.get("/v1/tickets/public").json()["items"]

    unpublished = client.patch(
        f"/v1/tickets/{created['ticketId']}/public",
        json={
            "publicStatus": "UNPUBLISHED",
            "publicDescription": "Published briefly.",
            "publicLocationLabel": "Hamra",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert unpublished.status_code == 200
    assert client.get("/v1/tickets/public").json()["items"] == []
    assert client.get(f"/v1/tickets/public/{created['ticketNumber']}").status_code == 404
