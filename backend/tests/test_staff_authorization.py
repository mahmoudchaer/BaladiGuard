"""API authorization checks for staff actions (issue #72)."""

from __future__ import annotations

import time

from app.config import get_settings
from app.core.staff_auth import issue_staff_access_token
from tests.test_submit_ticket import VALID_PAYLOAD


def _create_ticket(client) -> dict:
    # Public citizen submit — works with or without auth headers.
    response = client.post("/v1/tickets", json=VALID_PAYLOAD)
    assert response.status_code == 201
    return response.json()


def _assert_unauthorized(response) -> None:
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    # Failures must not leak ticket contents or internal identifiers.
    serialized = str(body).lower()
    assert "tkt_" not in serialized
    assert "contact" not in serialized
    assert "description" not in serialized
    assert VALID_PAYLOAD["description"].lower() not in serialized


def test_staff_login_returns_bearer_token(anonymous_client):
    response = anonymous_client.post(
        "/v1/staff/login",
        json={"username": "staff", "password": "staff-demo-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tokenType"] == "Bearer"
    assert body["username"] == "staff"
    assert body["expiresIn"] == get_settings().staff_token_ttl_seconds
    assert isinstance(body["accessToken"], str) and len(body["accessToken"]) > 20


def test_staff_login_rejects_bad_password(anonymous_client):
    response = anonymous_client.post(
        "/v1/staff/login",
        json={"username": "staff", "password": "wrong-password"},
    )

    _assert_unauthorized(response)
    assert "password" in response.json()["error"]["message"].lower()


def test_list_tickets_requires_staff_auth(anonymous_client):
    _create_ticket(anonymous_client)

    response = anonymous_client.get("/v1/tickets")

    _assert_unauthorized(response)


def test_list_tickets_succeeds_with_staff_token(client):
    created = _create_ticket(client)

    response = client.get("/v1/tickets")

    assert response.status_code == 200
    tickets = response.json()
    assert any(ticket["ticketId"] == created["ticketId"] for ticket in tickets)


def test_get_ticket_requires_staff_auth_and_does_not_leak_existence(anonymous_client):
    created = _create_ticket(anonymous_client)

    missing = anonymous_client.get("/v1/tickets/tkt_missing_id")
    existing = anonymous_client.get(f"/v1/tickets/{created['ticketId']}")

    _assert_unauthorized(missing)
    _assert_unauthorized(existing)
    # Same error shape whether or not the ticket exists.
    assert missing.json()["error"]["code"] == existing.json()["error"]["code"]


def test_get_ticket_succeeds_with_staff_token(client):
    created = _create_ticket(client)

    response = client.get(f"/v1/tickets/{created['ticketId']}")

    assert response.status_code == 200
    assert response.json()["ticketId"] == created["ticketId"]


def test_update_status_requires_staff_auth(anonymous_client):
    created = _create_ticket(anonymous_client)

    response = anonymous_client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "UNDER_REVIEW"},
    )

    _assert_unauthorized(response)


def test_update_status_succeeds_with_staff_token(client):
    created = _create_ticket(client)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "UNDER_REVIEW", "updatedBy": "staff"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "UNDER_REVIEW"


def test_category_review_requires_staff_auth(anonymous_client):
    created = _create_ticket(anonymous_client)

    response = anonymous_client.patch(
        f"/v1/tickets/{created['ticketId']}/category",
        json={"finalCategory": "road_damage"},
    )

    _assert_unauthorized(response)


def test_category_review_succeeds_with_staff_token(client):
    created = _create_ticket(client)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/category",
        json={"finalCategory": "road_damage", "categoryReviewedBy": "staff"},
    )

    assert response.status_code == 200
    assert response.json()["ai"]["finalCategory"] == "road_damage"


def test_merge_requires_staff_auth(anonymous_client):
    main = _create_ticket(anonymous_client)
    duplicate = _create_ticket(anonymous_client)

    response = anonymous_client.post(
        "/v1/tickets/merge",
        json={
            "canonicalTicketId": main["ticketId"],
            "duplicateTicketIds": [duplicate["ticketId"]],
        },
    )

    _assert_unauthorized(response)


def test_merge_succeeds_with_staff_token(client):
    main = _create_ticket(client)
    duplicate = _create_ticket(client)

    response = client.post(
        "/v1/tickets/merge",
        json={
            "canonicalTicketId": main["ticketId"],
            "duplicateTicketIds": [duplicate["ticketId"]],
            "mergedBy": "staff",
        },
    )

    assert response.status_code == 200
    assert response.json()["duplicateGroupId"] is not None


def test_citizen_submit_remains_public(anonymous_client):
    response = anonymous_client.post("/v1/tickets", json=VALID_PAYLOAD)

    assert response.status_code == 201
    assert "ticketId" in response.json()


def test_citizen_tracking_lookup_remains_public(anonymous_client):
    created = _create_ticket(anonymous_client)

    response = anonymous_client.get(f"/v1/tickets/track/{created['trackingCode']}")

    assert response.status_code == 200
    body = response.json()
    assert body["trackingCode"] == created["trackingCode"]
    assert "contact" not in body
    assert "ticketId" not in body


def test_invalid_bearer_token_is_rejected(anonymous_client):
    response = anonymous_client.get(
        "/v1/tickets",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    _assert_unauthorized(response)


def test_expired_bearer_token_is_rejected(anonymous_client):
    settings = get_settings()
    # Issue a token that already expired one hour ago.
    token = issue_staff_access_token(
        "staff",
        settings=settings,
        now=int(time.time()) - settings.staff_token_ttl_seconds - 3600,
    )

    response = anonymous_client.get(
        "/v1/tickets",
        headers={"Authorization": f"Bearer {token}"},
    )

    _assert_unauthorized(response)


def test_department_assignment_auth_integration_point_is_documented():
    """#141 will mount department assignment behind require_staff.

    Guard the dependency export so future endpoints can reuse the same contract.
    """
    from app.core.staff_auth import require_staff

    assert callable(require_staff)
