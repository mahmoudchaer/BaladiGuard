"""Citizen privacy lifecycle: export, deletion/anonymization, cross-user privacy (#190)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.database.memory import ticket_store
from app.database.memory_citizen import citizen_store
from app.schemas.citizen import CitizenProfileUpdateRequest
from app.schemas.stored_ticket import StoredTicket
from app.schemas.ticket import ReportContact, ReportLocation
from app.services.citizens.service import (
    anonymized_phone_for,
    citizen_service,
    is_anonymized_citizen,
)


def _create_ready_citizen(
    *,
    phone: str = "+96170123456",
    full_name: str = "Ada Citizen",
    email: str | None = "ada@example.com",
) -> tuple[str, str]:
    user = citizen_service.create_citizen(phone=phone, full_name=full_name, email=email)
    citizen_service.update_profile(
        user.user_id,
        CitizenProfileUpdateRequest.model_validate(
            {
                "notificationPreferences": {
                    "ticketUpdates": "EMAIL",
                    "announcements": True,
                },
                "publicNameVisible": True,
            }
        ),
    )
    token = citizen_service.issue_session(user.user_id)
    return user.user_id, token


def _owned_ticket(user_id: str, *, ticket_id: str = "tkt_privacy_1") -> StoredTicket:
    created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    ticket = StoredTicket(
        ticketId=ticket_id,
        ticketNumber="BG-2026-9101",
        trackingCode="PRIV01",
        description="Broken sidewalk near the park entrance needs repair.",
        contact=ReportContact(name="Ada Citizen", phone="+96170123456", email="ada@example.com"),
        location=ReportLocation(
            latitude=33.89,
            longitude=35.5,
            addressText="Hamra, Beirut",
            source="MANUAL",
        ),
        imageObjectKey="reports/mock/privacy-sidewalk.jpg",
        ownerUserId=user_id,
        status="SUBMITTED",
        category="road_damage",
        createdAt=created_at,
        updatedAt=created_at,
    )
    ticket_store.save(ticket)
    return ticket


def test_export_requires_citizen_auth(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/v1/citizen/me/export")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_staff_token_cannot_export_or_delete(
    anonymous_client: TestClient,
    staff_auth_headers: dict[str, str],
) -> None:
    export_response = anonymous_client.get("/v1/citizen/me/export", headers=staff_auth_headers)
    delete_response = anonymous_client.post("/v1/citizen/me/delete", headers=staff_auth_headers)
    assert export_response.status_code == 401
    assert delete_response.status_code == 401


def test_export_returns_profile_and_owned_tickets_only(anonymous_client: TestClient) -> None:
    user_id, token = _create_ready_citizen()
    other_id, _other_token = _create_ready_citizen(phone="+96171111111", full_name="Other")
    _owned_ticket(user_id)
    _owned_ticket(other_id, ticket_id="tkt_privacy_other")

    response = anonymous_client.get(
        "/v1/citizen/me/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["profile"]["userId"] == user_id
    assert body["profile"]["email"] == "ada@example.com"
    assert body["exportedAt"]
    assert len(body["tickets"]) == 1
    assert body["tickets"][0]["ticketId"] == "tkt_privacy_1"
    assert body["tickets"][0]["trackingCode"] == "PRIV01"
    assert body["tickets"][0]["locationAddress"] == "Hamra, Beirut"
    assert all(item["ticketId"] != "tkt_privacy_other" for item in body["tickets"])


def test_cross_user_cannot_export_another_account(anonymous_client: TestClient) -> None:
    owner_id, _owner_token = _create_ready_citizen(phone="+96170111111")
    _owned_ticket(owner_id)
    _intruder_id, intruder_token = _create_ready_citizen(
        phone="+96170222222",
        full_name="Intruder",
    )

    response = anonymous_client.get(
        "/v1/citizen/me/export",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["userId"] != owner_id
    assert body["tickets"] == []


def test_delete_anonymizes_pii_and_revokes_sessions(anonymous_client: TestClient) -> None:
    user_id, token = _create_ready_citizen()
    second_token = citizen_service.issue_session(user_id)
    ticket = _owned_ticket(user_id)
    original_contact = ticket.contact.model_copy(deep=True)

    response = anonymous_client.post(
        "/v1/citizen/me/delete",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "deleted"
    assert body["userId"] == user_id
    assert body["deletedAt"]

    stored = citizen_store.get(user_id)
    assert stored is not None
    assert is_anonymized_citizen(stored)
    assert stored.phone == anonymized_phone_for(user_id)
    assert stored.full_name is None
    assert stored.email is None
    assert stored.public_name_visible is False
    assert stored.active is False
    assert stored.notification_preferences.ticket_updates == "NONE"
    assert stored.notification_preferences.announcements is False
    assert citizen_store.get_by_phone("+96170123456") is None

    me_response = anonymous_client.get(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    other_session = anonymous_client.get(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {second_token}"},
    )
    assert me_response.status_code == 401
    assert other_session.status_code == 401

    retained = ticket_store.get(ticket.ticket_id)
    assert retained is not None
    assert retained.owner_user_id == user_id
    assert retained.status == "SUBMITTED"
    assert retained.category == "road_damage"
    assert retained.location.address_text == "Hamra, Beirut"
    assert retained.contact == original_contact
    assert retained.image_object_key == "reports/mock/privacy-sidewalk.jpg"


def test_deleted_phone_can_be_reclaimed_by_new_account(anonymous_client: TestClient) -> None:
    user_id, token = _create_ready_citizen(phone="+96170333444", full_name="Old Owner")
    delete_response = anonymous_client.post(
        "/v1/citizen/me/delete",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 200

    replacement = citizen_service.create_citizen(
        phone="+96170333444",
        full_name="New Owner",
    )
    assert replacement.user_id != user_id
    assert replacement.phone == "+96170333444"
    assert replacement.active is True
    tombstone = citizen_store.get(user_id)
    assert tombstone is not None
    assert is_anonymized_citizen(tombstone)


def test_delete_requires_auth(anonymous_client: TestClient) -> None:
    response = anonymous_client.post("/v1/citizen/me/delete")
    assert response.status_code == 401
