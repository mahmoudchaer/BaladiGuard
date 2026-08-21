"""Individual staff accounts, roles, logout, and session expiry (issue #175)."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.password_hashing import hash_password, verify_password
from app.core.staff_auth import (
    deactivate_staff_account,
    issue_staff_access_token,
    principal_from_user,
    verify_staff_access_token,
)
from app.database.memory_staff import staff_store
from app.schemas.staff_user import StoredStaffUser
from app.services.staff.bootstrap import BEIRUT_MUNICIPALITY_ID


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("staff-demo-password")
    second = hash_password("staff-demo-password")
    assert first != second
    assert verify_password("staff-demo-password", first)
    assert not verify_password("wrong-password", first)
    assert "staff-demo-password" not in first


def test_staff_login_returns_role_aware_claims(anonymous_client: TestClient) -> None:
    response = anonymous_client.post(
        "/v1/staff/login",
        json={"username": "staff", "password": "staff-demo-password"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tokenType"] == "Bearer"
    assert body["username"] == "staff"
    assert body["staffId"] == "staff_muni_001"
    assert body["name"] == "Demo Municipal Staff"
    assert body["role"] == "municipal_staff"
    assert body["municipalityId"] == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    assert body["departmentIds"] == [
        "d1111111-1111-1111-1111-111111111111",
        "d3333333-3333-3333-3333-333333333333",
    ]
    assert body["expiresIn"] == get_settings().staff_token_ttl_seconds
    assert "password" not in str(body).lower()
    assert "passwordHash" not in body


def test_admin_login_returns_municipality_scope(anonymous_client: TestClient) -> None:
    response = anonymous_client.post(
        "/v1/staff/login",
        json={"username": "admin", "password": "staff-demo-password"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "administrator"
    assert body["municipalityId"] == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    assert body["departmentIds"] is None


def test_staff_login_rejects_invalid_credentials(anonymous_client: TestClient) -> None:
    response = anonymous_client.post(
        "/v1/staff/login",
        json={"username": "staff", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_inactive_staff_cannot_login(anonymous_client: TestClient) -> None:
    user = staff_store.get_by_username("staff")
    assert user is not None
    deactivate_staff_account(user.staff_id)

    response = anonymous_client.post(
        "/v1/staff/login",
        json={"username": "staff", "password": "staff-demo-password"},
    )
    assert response.status_code == 401
    # Same generic message as bad password — do not reveal inactive state.
    assert response.json()["error"]["message"] == "Invalid staff username or password."


def test_token_carries_role_claims_on_verify() -> None:
    user = staff_store.get_by_username("admin")
    assert user is not None
    principal = principal_from_user(user)
    token = issue_staff_access_token(principal)
    verified = verify_staff_access_token(token)
    assert verified.staff_id == user.staff_id
    assert verified.role == "administrator"
    assert verified.municipality_id == BEIRUT_MUNICIPALITY_ID
    assert verified.department_ids is None


def test_logout_revokes_existing_token(anonymous_client: TestClient) -> None:
    login = anonymous_client.post(
        "/v1/staff/login",
        json={"username": "staff", "password": "staff-demo-password"},
    )
    assert login.status_code == 200
    token = login.json()["accessToken"]

    logout = anonymous_client.post(
        "/v1/staff/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout.status_code == 204

    blocked = anonymous_client.get(
        "/v1/tickets",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert blocked.status_code == 401


def test_expired_token_is_rejected(anonymous_client: TestClient) -> None:
    user = staff_store.get_by_username("staff")
    assert user is not None
    settings = get_settings()
    token = issue_staff_access_token(
        principal_from_user(user),
        settings=settings,
        now=int(time.time()) - settings.staff_token_ttl_seconds - 3600,
    )
    response = anonymous_client.get(
        "/v1/tickets",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_deactivation_revokes_outstanding_sessions(anonymous_client: TestClient) -> None:
    login = anonymous_client.post(
        "/v1/staff/login",
        json={"username": "staff", "password": "staff-demo-password"},
    )
    token = login.json()["accessToken"]
    user = staff_store.get_by_username("staff")
    assert user is not None
    deactivate_staff_account(user.staff_id)

    response = anonymous_client.get(
        "/v1/tickets",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_staff_record_never_serializes_password_in_public_helpers() -> None:
    user = staff_store.get_by_username("staff")
    assert user is not None
    dumped = user.model_dump(by_alias=True)
    assert "passwordHash" in dumped
    # API login response must not include credential metadata.
    assert isinstance(dumped["passwordHash"], str)
    assert not dumped["passwordHash"].startswith("staff-demo")


def test_username_claim_is_unique() -> None:
    stamped = "2026-08-01T00:00:00Z"
    duplicate = StoredStaffUser(
        staffId="staff_dup_001",
        username="staff",
        name="Duplicate",
        email="dup@example.com",
        passwordHash=hash_password("other-password"),
        role="municipal_staff",
        municipalityId="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        departmentIds=["d1111111-1111-1111-1111-111111111111"],
        active=True,
        createdAt=stamped,
        updatedAt=stamped,
    )
    try:
        staff_store.create(duplicate)
        raise AssertionError("expected username conflict")
    except Exception as exc:
        assert "claimed" in str(exc).lower() or "already" in str(exc).lower()
