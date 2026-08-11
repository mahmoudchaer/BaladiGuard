"""Sprint 6 full MVP flow acceptance (issue #49).

One automated pass of the complete product path used by Sprint 6 demos:
citizen identity → contribution-ready profile → report submit → tracking/history
isolation → staff login/scoped work → status updates → merge → mock notifications.

Deployed infra, security scans, and DR are out of scope (dedicated tickets).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.database.memory import ticket_store
from app.services.citizens.service import citizen_service
from app.services.notifications.adapters import MockNotificationAdapter
from tests.conftest import (
    ensure_contribution_ready_citizen,
    issue_test_staff_token,
)
from tests.test_submit_ticket import VALID_PAYLOAD

STREET_LIGHTING = "d3333333-3333-3333-3333-333333333333"
CITIZEN_A_PHONE = "+96170110001"
CITIZEN_B_PHONE = "+96170110002"


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _otp_login(
    client: TestClient,
    *,
    phone: str,
    full_name: str | None = None,
) -> dict:
    requested = client.post(
        "/v1/citizen/auth/otp/request",
        json={"phone": phone, "purpose": "LOGIN_OR_SIGNUP"},
    )
    assert requested.status_code == 202, requested.text
    challenge_id = requested.json()["challengeId"]
    code = citizen_service.peek_dev_otp_code(challenge_id)
    assert code is not None
    body: dict = {"challengeId": challenge_id, "code": code}
    if full_name is not None:
        body["fullName"] = full_name
    verified = client.post("/v1/citizen/auth/otp/verify", json=body)
    assert verified.status_code == 200, verified.text
    return verified.json()


def _submit(client: TestClient, headers: dict[str, str], **overrides: object) -> dict:
    payload = {**VALID_PAYLOAD, **overrides}
    response = client.post("/v1/tickets", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_sprint6_full_mvp_flow_acceptance(anonymous_client: TestClient, monkeypatch) -> None:
    delivered: list[tuple[str, str, str | None]] = []
    original = MockNotificationAdapter.deliver

    def capture(self, message, recipient=None):
        delivered.append(
            (
                message.event,
                message.status,
                recipient.phone if recipient else None,
            )
        )
        return original(self, message, recipient)

    monkeypatch.setattr(MockNotificationAdapter, "deliver", capture)

    # --- Citizen A: signup (new OTP) with full name → contribution-ready ---
    signup = _otp_login(
        anonymous_client,
        phone=CITIZEN_A_PHONE,
        full_name="Ada Demo Citizen",
    )
    token_a = signup["accessToken"]
    user_a_id = signup["userId"]
    assert signup["contributionReady"] is True
    headers_a = _auth_headers(token_a)

    # Session restore via GET /me
    me = anonymous_client.get("/v1/citizen/me", headers=headers_a)
    assert me.status_code == 200
    assert me.json()["userId"] == user_a_id
    assert me.json()["phone"] == CITIZEN_A_PHONE

    # Profile update (email + notification preference)
    patched = anonymous_client.patch(
        "/v1/citizen/me",
        headers=headers_a,
        json={
            "email": "ada-demo@example.com",
            "notificationPreferences": {"ticketUpdates": "SMS"},
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["email"] == "ada-demo@example.com"
    assert patched.json()["notificationPreferences"]["ticketUpdates"] == "SMS"

    # Validation: empty name rejected
    bad_name = anonymous_client.patch(
        "/v1/citizen/me",
        headers=headers_a,
        json={"fullName": "  "},
    )
    assert bad_name.status_code == 400
    assert bad_name.json()["error"]["code"] in {"VALIDATION_ERROR", "INVALID_FULL_NAME"}

    # --- Citizen B for cross-tenant isolation ---
    user_b, token_b = ensure_contribution_ready_citizen(
        phone=CITIZEN_B_PHONE,
        full_name="Bob Other Citizen",
        email="bob@example.com",
    )
    headers_b = _auth_headers(token_b)

    # Empty history for A before submit
    empty_history = anonymous_client.get("/v1/citizen/me/tickets", headers=headers_a)
    assert empty_history.status_code == 200
    empty_body = empty_history.json()
    assert empty_body["items"] == []
    assert empty_body.get("nextCursor") is None

    # Incomplete profile cannot submit
    bare = citizen_service.create_citizen(phone="+96170999880")
    bare_token = citizen_service.issue_session(bare.user_id)
    incomplete_submit = anonymous_client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=_auth_headers(bare_token),
    )
    assert incomplete_submit.status_code == 403
    assert incomplete_submit.json()["error"]["code"] == "CONTRIBUTION_PROFILE_REQUIRED"

    # Unauthenticated submit rejected
    guest_submit = anonymous_client.post("/v1/tickets", json=VALID_PAYLOAD)
    assert guest_submit.status_code == 401

    # --- Submit reports (linked to owners) ---
    created_a = _submit(
        anonymous_client,
        headers_a,
        description="Sprint6 pothole near campus for citizen A acceptance flow.",
    )
    created_a_dup = _submit(
        anonymous_client,
        headers_a,
        description="Sprint6 near-dupe pothole for merge acceptance flow A.",
        imageObjectKey="reports/temp/01JZABCDEF/photo-a2.jpg",
    )
    created_b = _submit(
        anonymous_client,
        headers_b,
        description="Sprint6 lighting issue owned only by citizen B.",
        imageObjectKey="reports/temp/01JZABCDEF/photo-b.jpg",
    )

    stored_a = ticket_store.get(created_a["ticketId"])
    assert stored_a is not None
    assert stored_a.owner_user_id == user_a_id
    stored_b = ticket_store.get(created_b["ticketId"])
    assert stored_b is not None
    assert stored_b.owner_user_id == user_b.user_id

    # History: A sees only A tickets
    history_a = anonymous_client.get("/v1/citizen/me/tickets", headers=headers_a)
    assert history_a.status_code == 200
    history_items = history_a.json()["items"]
    history_codes = {item["trackingCode"] for item in history_items}
    assert created_a["trackingCode"] in history_codes
    assert created_a_dup["trackingCode"] in history_codes
    assert created_b["trackingCode"] not in history_codes
    for item in history_items:
        assert set(item.keys()) <= {
            "trackingCode",
            "status",
            "category",
            "locationAddress",
            "submittedAt",
        }
        assert "ownerUserId" not in item
        assert "contact" not in item

    # Public tracking is safe (no PII / owner)
    track = anonymous_client.get(f"/v1/tickets/track/{created_a['trackingCode']}")
    assert track.status_code == 200
    track_body = track.json()
    assert track_body["trackingCode"] == created_a["trackingCode"]
    assert "ownerUserId" not in track_body
    assert "contact" not in track_body
    assert CITIZEN_A_PHONE not in str(track_body)
    assert "ada-demo@example.com" not in str(track_body)

    # Citizen cannot use staff routes
    citizen_as_staff = anonymous_client.get("/v1/tickets", headers=headers_a)
    assert citizen_as_staff.status_code == 401

    # --- Staff login + protected routes ---
    unauth_list = anonymous_client.get("/v1/tickets")
    assert unauth_list.status_code == 401

    staff_login = anonymous_client.post(
        "/v1/staff/login",
        json={"username": "admin", "password": "staff-demo-password"},
    )
    assert staff_login.status_code == 200, staff_login.text
    staff_token = staff_login.json()["accessToken"]
    staff_headers = _auth_headers(staff_token)
    assert staff_login.json().get("role") is not None

    bad_staff = anonymous_client.post(
        "/v1/staff/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert bad_staff.status_code == 401

    listed = anonymous_client.get("/v1/tickets", headers=staff_headers)
    assert listed.status_code == 200
    staff_ids = {row["ticketId"] for row in listed.json()["items"]}
    assert created_a["ticketId"] in staff_ids
    assert created_b["ticketId"] in staff_ids

    detail = anonymous_client.get(
        f"/v1/tickets/{created_a['ticketId']}",
        headers=staff_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["ownerUserId"] == user_a_id

    # Review + assign + status (staff workflow)
    review = anonymous_client.patch(
        f"/v1/tickets/{created_a['ticketId']}/category",
        headers=staff_headers,
        json={"finalCategory": "road_damage", "categoryReviewedBy": "ignore-client"},
    )
    assert review.status_code == 200, review.text

    for ticket_id in (created_a["ticketId"], created_a_dup["ticketId"]):
        assign = anonymous_client.patch(
            f"/v1/tickets/{ticket_id}/department",
            headers=staff_headers,
            json={"departmentId": STREET_LIGHTING, "updatedBy": "ignore-client"},
        )
        assert assign.status_code == 200, assign.text

    under_review = anonymous_client.patch(
        f"/v1/tickets/{created_a['ticketId']}/status",
        headers=staff_headers,
        json={"status": "UNDER_REVIEW", "updatedBy": "ignore-client"},
    )
    assert under_review.status_code == 200, under_review.text
    assert under_review.json()["status"] == "UNDER_REVIEW"

    assigned = anonymous_client.patch(
        f"/v1/tickets/{created_a['ticketId']}/status",
        headers=staff_headers,
        json={"status": "ASSIGNED", "updatedBy": "ignore-client"},
    )
    assert assigned.status_code == 200, assigned.text

    # Merge within scope (shared final category path via submit AI/default tests)
    for ticket_id in (created_a["ticketId"], created_a_dup["ticketId"]):
        cat = anonymous_client.patch(
            f"/v1/tickets/{ticket_id}/category",
            headers=staff_headers,
            json={"finalCategory": "road_damage", "categoryReviewedBy": "staff"},
        )
        assert cat.status_code == 200, cat.text

    merge = anonymous_client.post(
        "/v1/tickets/merge",
        headers=staff_headers,
        json={
            "canonicalTicketId": created_a["ticketId"],
            "duplicateTicketIds": [created_a_dup["ticketId"]],
            "mergedBy": "ignored",
        },
    )
    assert merge.status_code == 200, merge.text
    assert merge.json()["duplicateGroupId"] is not None

    # Tracking still safe after staff updates
    track_after = anonymous_client.get(f"/v1/tickets/track/{created_a['trackingCode']}")
    assert track_after.status_code == 200
    assert track_after.json()["status"] == "ASSIGNED"
    assert "ownerUserId" not in track_after.json()

    # Notifications: created + status updates (mock adapter)
    events_only = [event for event, _status, _phone in delivered]
    assert "ticket_created" in events_only
    assert "ticket_updated" in events_only

    phones_for_a = [phone for _event, _status, phone in delivered if phone == CITIZEN_A_PHONE]
    assert phones_for_a, "expected mock delivery to citizen A phone"

    # Logout citizen A; session restore fails
    logout = anonymous_client.post("/v1/citizen/auth/logout", headers=headers_a)
    assert logout.status_code == 204
    after_logout = anonymous_client.get("/v1/citizen/me", headers=headers_a)
    assert after_logout.status_code == 401

    # Staff logout
    staff_logout = anonymous_client.post("/v1/staff/logout", headers=staff_headers)
    assert staff_logout.status_code in {200, 204}
    staff_after = anonymous_client.get("/v1/tickets", headers=staff_headers)
    assert staff_after.status_code == 401

    # Municipal staff still usable via helper (scope smoke)
    municipal_token = issue_test_staff_token(anonymous_client, username="staff")
    municipal_list = anonymous_client.get(
        "/v1/tickets",
        headers=_auth_headers(municipal_token),
    )
    assert municipal_list.status_code == 200
