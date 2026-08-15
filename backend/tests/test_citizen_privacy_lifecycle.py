"""Citizen privacy lifecycle: export, deletion/anonymization, cross-user privacy (#190)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.core.citizen_auth import issue_citizen_session
from app.database.memory import ticket_store
from app.database.memory_citizen import citizen_store
from app.database.memory_citizen_session import citizen_session_store
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


def _owned_ticket(
    user_id: str | None,
    *,
    ticket_id: str = "tkt_privacy_1",
    tracking_code: str = "PRIV01",
    created_at: str | None = None,
    status: str = "SUBMITTED",
    category: str = "road_damage",
    final_category: str | None = None,
    contact: ReportContact | None = None,
) -> StoredTicket:
    created_at = created_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    ticket = StoredTicket(
        ticketId=ticket_id,
        ticketNumber="BG-2026-9101",
        trackingCode=tracking_code,
        description="Broken sidewalk near the park entrance needs repair.",
        contact=contact
        or ReportContact(name="Ada Citizen", phone="+96170123456", email="ada@example.com"),
        location=ReportLocation(
            latitude=33.89,
            longitude=35.5,
            addressText="Hamra, Beirut",
            source="MANUAL",
        ),
        imageObjectKey="reports/mock/privacy-sidewalk.jpg",
        ownerUserId=user_id,
        status=status,
        category=category,
        finalCategory=final_category,
        createdAt=created_at,
        updatedAt=created_at,
        updatedBy="staff-secret",
        departmentId="dept-private",
        municipalityId="muni-private",
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


def test_ticket_history_requires_citizen_auth(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/v1/citizen/me/tickets")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_staff_token_cannot_read_citizen_ticket_history(
    anonymous_client: TestClient,
    staff_auth_headers: dict[str, str],
) -> None:
    response = anonymous_client.get("/v1/citizen/me/tickets", headers=staff_auth_headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_ticket_history_returns_owned_citizen_safe_tickets_only(
    anonymous_client: TestClient,
) -> None:
    user_id, token = _create_ready_citizen()
    other_id, _other_token = _create_ready_citizen(phone="+96171111111", full_name="Other")
    _owned_ticket(
        user_id,
        final_category="sidewalk_damage",
        contact=ReportContact(
            name="Private Name",
            phone="+96170123456",
            email="private@example.com",
            preferredChannel="EMAIL",
        ),
    )
    _owned_ticket(other_id, ticket_id="tkt_other", tracking_code="OTHER2")
    _owned_ticket(None, ticket_id="tkt_legacy", tracking_code="LEGACY")

    response = anonymous_client.get(
        "/v1/citizen/me/tickets",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["nextCursor"] is None
    assert body["limit"] == 20
    assert body["items"] == [
        {
            "trackingCode": "PRIV01",
            "status": "SUBMITTED",
            "category": "sidewalk_damage",
            "locationAddress": "Hamra, Beirut",
            "submittedAt": body["items"][0]["submittedAt"],
            "canSubmitResolutionFeedback": False,
            "resolutionFeedbackStatus": None,
        }
    ]
    assert body["items"][0]["submittedAt"]
    serialized = str(body)
    for forbidden in (
        "ticketId",
        "ownerUserId",
        "contact",
        "phone",
        "email",
        "publicNameVisible",
        "updatedBy",
        "departmentId",
        "municipalityId",
        "staff-secret",
        "private@example.com",
    ):
        assert forbidden not in serialized


def test_ticket_history_orders_newest_first_with_pagination(
    anonymous_client: TestClient,
) -> None:
    user_id, token = _create_ready_citizen()
    _owned_ticket(
        user_id,
        ticket_id="tkt_old",
        tracking_code="OLD222",
        created_at="2026-08-01T09:00:00Z",
    )
    _owned_ticket(
        user_id,
        ticket_id="tkt_tie_a",
        tracking_code="TIEAAA",
        created_at="2026-08-02T09:00:00Z",
    )
    _owned_ticket(
        user_id,
        ticket_id="tkt_tie_z",
        tracking_code="TIEZZZ",
        created_at="2026-08-02T09:00:00Z",
    )

    first = anonymous_client.get(
        "/v1/citizen/me/tickets?limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert [item["trackingCode"] for item in first_body["items"]] == ["TIEZZZ", "TIEAAA"]
    assert first_body["nextCursor"]

    second = anonymous_client.get(
        f"/v1/citizen/me/tickets?limit=2&cursor={first_body['nextCursor']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert [item["trackingCode"] for item in second_body["items"]] == ["OLD222"]
    assert second_body["nextCursor"] is None


def test_ticket_history_cursor_is_stable_when_newer_ticket_is_inserted(
    anonymous_client: TestClient,
) -> None:
    user_id, token = _create_ready_citizen()
    _owned_ticket(
        user_id,
        ticket_id="tkt_oldest",
        tracking_code="OLD111",
        created_at="2026-08-01T09:00:00Z",
    )
    _owned_ticket(
        user_id,
        ticket_id="tkt_middle",
        tracking_code="MID222",
        created_at="2026-08-02T09:00:00Z",
    )
    _owned_ticket(
        user_id,
        ticket_id="tkt_newest",
        tracking_code="NEW333",
        created_at="2026-08-03T09:00:00Z",
    )

    first = anonymous_client.get(
        "/v1/citizen/me/tickets?limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert [item["trackingCode"] for item in first_body["items"]] == ["NEW333", "MID222"]
    assert first_body["nextCursor"]

    _owned_ticket(
        user_id,
        ticket_id="tkt_inserted_newer",
        tracking_code="INS444",
        created_at="2026-08-04T09:00:00Z",
    )

    second = anonymous_client.get(
        f"/v1/citizen/me/tickets?limit=2&cursor={first_body['nextCursor']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert [item["trackingCode"] for item in second_body["items"]] == ["OLD111"]
    assert second_body["nextCursor"] is None


def test_ticket_history_empty_is_success(anonymous_client: TestClient) -> None:
    _user_id, token = _create_ready_citizen()

    response = anonymous_client.get(
        "/v1/citizen/me/tickets",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "nextCursor": None, "limit": 20}


def test_ticket_history_rejects_invalid_cursor(anonymous_client: TestClient) -> None:
    _user_id, token = _create_ready_citizen()

    response = anonymous_client.get(
        "/v1/citizen/me/tickets?cursor=another-user",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_revoked_session_cannot_read_ticket_history(anonymous_client: TestClient) -> None:
    user_id, token = _create_ready_citizen()
    _owned_ticket(user_id)
    citizen_service.logout_session(token.partition(".")[0])

    response = anonymous_client.get(
        "/v1/citizen/me/tickets",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_expired_session_cannot_read_ticket_history(anonymous_client: TestClient) -> None:
    user_id, _token = _create_ready_citizen()
    expired_token, _session = issue_citizen_session(
        user_id,
        session_store=citizen_session_store,
        now=datetime.now(UTC) - timedelta(days=31),
    )
    _owned_ticket(user_id)

    response = anonymous_client.get(
        "/v1/citizen/me/tickets",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
