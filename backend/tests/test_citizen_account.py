"""Citizen account persistence and profile API tests (issue #169)."""

from __future__ import annotations

import concurrent.futures

from fastapi.testclient import TestClient

from app.database.memory_citizen import citizen_store
from app.database.memory_citizen_session import citizen_session_store
from app.schemas.citizen import CitizenProfileUpdateRequest, StoredCitizenUser
from app.services.citizens.service import CitizenServiceError, citizen_service


def _create_ready_citizen(
    *,
    phone: str = "+96170123456",
    full_name: str = "Ada Citizen",
    email: str | None = None,
) -> tuple[StoredCitizenUser, str]:
    user = citizen_service.create_citizen(phone=phone, full_name=full_name, email=email)
    token = citizen_service.issue_session(user.user_id)
    return user, token


def test_create_and_canonical_lookup() -> None:
    created = citizen_service.create_citizen(phone="+961 70 123 456", full_name="Ada")
    by_e164 = citizen_service.get_by_phone("+96170123456")
    by_national = citizen_service.get_by_phone("70 123 456", region="LB")

    assert created.user_id.startswith("usr_")
    assert created.phone == "+96170123456"
    assert created.phone_verified_at
    assert created.email is None
    assert created.notification_preferences.ticket_updates == "NONE"
    assert created.public_name_visible is False
    assert created.active is True
    assert by_e164 is not None and by_e164.user_id == created.user_id
    assert by_national is not None and by_national.user_id == created.user_id
    assert "password" not in created.model_dump(by_alias=True)


def test_duplicate_phone_claim_rejected() -> None:
    citizen_service.create_citizen(phone="+96170111111", full_name="First")
    try:
        citizen_service.create_citizen(phone="70 111 111", region="LB", full_name="Second")
        raise AssertionError("expected PhoneClaimConflict")
    except CitizenServiceError as exc:
        assert exc.code == "PHONE_UNAVAILABLE"
        assert exc.status_code == 409


def test_concurrent_phone_claims_have_single_winner() -> None:
    def attempt(index: int) -> str | None:
        try:
            user = citizen_service.create_citizen(
                phone="+96170999999",
                full_name=f"Racer {index}",
            )
            return user.user_id
        except CitizenServiceError as exc:
            assert exc.code == "PHONE_UNAVAILABLE"
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))

    winners = [user_id for user_id in results if user_id is not None]
    assert len(winners) == 1
    assert citizen_store.get_by_phone("+96170999999") is not None


def test_get_profile_returns_citizen_safe_fields_and_contribution_ready(
    anonymous_client: TestClient,
) -> None:
    user, token = _create_ready_citizen()
    response = anonymous_client.get(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["userId"] == user.user_id
    assert body["phone"] == "+96170123456"
    assert body["fullName"] == "Ada Citizen"
    assert body["contributionReady"] is True
    assert body["publicNameVisible"] is False
    assert "password" not in body
    assert "tokenHash" not in body
    assert "codeHash" not in body
    assert "sessionId" not in body


def test_incomplete_profile_is_not_contribution_ready(anonymous_client: TestClient) -> None:
    user = citizen_service.create_citizen(phone="+96170123456")
    token = citizen_service.issue_session(user.user_id)
    response = anonymous_client.get(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["contributionReady"] is False
    assert response.json()["fullName"] is None


def test_partial_profile_update(anonymous_client: TestClient) -> None:
    _user, token = _create_ready_citizen()
    response = anonymous_client.patch(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "fullName": "  Ada Updated  ",
            "email": "ada@example.com",
            "publicNameVisible": True,
            "notificationPreferences": {
                "ticketUpdates": "EMAIL",
                "announcements": True,
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fullName"] == "Ada Updated"
    assert body["email"] == "ada@example.com"
    assert body["publicNameVisible"] is True
    assert body["notificationPreferences"]["ticketUpdates"] == "EMAIL"
    assert body["notificationPreferences"]["announcements"] is True
    assert body["contributionReady"] is True


def test_email_is_nullable_and_non_unique() -> None:
    first = citizen_service.create_citizen(
        phone="+96170100001",
        full_name="One",
        email="shared@example.com",
    )
    second = citizen_service.create_citizen(
        phone="+96170100002",
        full_name="Two",
        email="shared@example.com",
    )
    assert first.email == second.email == "shared@example.com"


def test_rejected_update_empty_name(anonymous_client: TestClient) -> None:
    _user, token = _create_ready_citizen()
    response = anonymous_client.patch(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"fullName": "   "},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_rejected_email_preference_without_email(anonymous_client: TestClient) -> None:
    _user, token = _create_ready_citizen()
    response = anonymous_client.patch(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"notificationPreferences": {"ticketUpdates": "EMAIL"}},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_verified_phone_change_transfers_claim_and_revokes_sessions(
    anonymous_client: TestClient,
) -> None:
    user, token = _create_ready_citizen(phone="+96170123456")
    other_token = citizen_service.issue_session(user.user_id)
    challenge_id, code = citizen_service.create_change_phone_challenge(
        user_id=user.user_id,
        phone="71 222 333",
        region="LB",
    )

    response = anonymous_client.patch(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "phone": "71 222 333",
            "region": "LB",
            "phoneChangeChallengeId": challenge_id,
            "phoneChangeCode": code,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["phone"] == "+96171222333"

    assert citizen_service.get_by_phone("+96170123456") is None
    assert citizen_service.get_by_phone("+96171222333") is not None

    for stale in (token, other_token):
        stale_response = anonymous_client.get(
            "/v1/citizen/me",
            headers={"Authorization": f"Bearer {stale}"},
        )
        assert stale_response.status_code == 401
        assert stale_response.headers.get("www-authenticate", "").lower().startswith("bearer")


def test_phone_change_rejects_claimed_number(anonymous_client: TestClient) -> None:
    _owner, _ = _create_ready_citizen(phone="+96170111111", full_name="Owner")
    user, token = _create_ready_citizen(phone="+96170222222", full_name="Changer")
    challenge_id, code = citizen_service.create_change_phone_challenge(
        user_id=user.user_id,
        phone="+96170111111",
    )
    response = anonymous_client.patch(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "phone": "+96170111111",
            "phoneChangeChallengeId": challenge_id,
            "phoneChangeCode": code,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PHONE_UNAVAILABLE"
    assert citizen_service.get_by_phone("+96170222222") is not None


def test_phone_change_rejects_wrong_otp(anonymous_client: TestClient) -> None:
    user, token = _create_ready_citizen()
    challenge_id, _code = citizen_service.create_change_phone_challenge(
        user_id=user.user_id,
        phone="+96171999999",
    )
    response = anonymous_client.patch(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "phone": "+96171999999",
            "phoneChangeChallengeId": challenge_id,
            "phoneChangeCode": "000000",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_OTP"


def test_missing_user_session_returns_401(anonymous_client: TestClient) -> None:
    user, token = _create_ready_citizen()
    citizen_store.clear()
    citizen_session_store.clear()
    # Recreate a dangling session pointing at a deleted user.
    token = citizen_service.issue_session(user.user_id)
    # user row is gone
    response = anonymous_client.get(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Session exists but user is missing → unauthorized per profile contract.
    assert response.status_code == 401


def test_staff_token_cannot_access_citizen_profile(
    anonymous_client: TestClient,
    staff_auth_headers: dict[str, str],
) -> None:
    response = anonymous_client.get("/v1/citizen/me", headers=staff_auth_headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_unauthenticated_profile_returns_401(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/v1/citizen/me")
    assert response.status_code == 401


def test_tickets_can_reference_owner_user_id_without_session_material() -> None:
    from datetime import UTC, datetime

    from app.database.memory import ticket_store
    from app.schemas.stored_ticket import StoredTicket
    from app.schemas.ticket import ReportContact, ReportLocation

    user = citizen_service.create_citizen(phone="+96170333333", full_name="Owner")
    created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    ticket = StoredTicket(
        ticketId="tkt_owner_ref",
        ticketNumber="BG-2026-9001",
        trackingCode="OWNREF",
        description="Pothole",
        contact=ReportContact(name="Owner", phone=user.phone),
        location=ReportLocation(
            latitude=33.89,
            longitude=35.5,
            addressText="Beirut",
            source="MANUAL",
        ),
        imageObjectKey="reports/mock/x.jpg",
        ownerUserId=user.user_id,
        status="SUBMITTED",
        createdAt=created_at,
        updatedAt=created_at,
    )
    ticket_store.save(ticket)
    loaded = ticket_store.get("tkt_owner_ref")
    assert loaded is not None
    assert loaded.owner_user_id == user.user_id
    dumped = loaded.model_dump(by_alias=True)
    assert "otp" not in str(dumped).lower()
    assert "session" not in str(dumped).lower()


def test_update_request_requires_challenge_for_phone_change() -> None:
    try:
        CitizenProfileUpdateRequest.model_validate({"phone": "+96171999999"})
        raise AssertionError("expected validation error")
    except Exception as exc:  # pydantic ValidationError
        assert "phoneChangeChallengeId" in str(exc)
