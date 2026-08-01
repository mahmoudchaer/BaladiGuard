"""DynamoDB-backed staff account store tests (issue #175)."""

from __future__ import annotations

from app.config import Settings
from app.core.password_hashing import hash_password
from app.core.staff_auth import (
    authenticate_staff_credentials,
    issue_staff_access_token,
    revoke_staff_sessions,
    verify_staff_access_token,
)
from app.database.dynamo_staff_store import DynamoStaffStore
from app.database.dynamodb_tables import TABLE_DEFINITIONS
from app.services.staff.bootstrap import ensure_demo_staff_accounts


def test_staff_tables_are_defined() -> None:
    suffixes = {item["suffix"] for item in TABLE_DEFINITIONS}
    assert "staff-users" in suffixes
    assert "staff-username-claims" in suffixes
    assert "staff-password-reset-challenges" in suffixes


def test_dynamo_staff_get_uses_consistent_read(
    dynamodb_settings: Settings,
    monkeypatch,
) -> None:
    store = DynamoStaffStore(dynamodb_settings)
    captured: dict[str, object] = {}

    def fake_get_item(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(store._users_table, "get_item", fake_get_item)
    assert store.get("staff_missing") is None
    assert captured["Key"] == {"staffId": "staff_missing"}
    assert captured["ConsistentRead"] is True


def test_dynamo_demo_staff_login_and_logout_revokes_token(dynamodb_settings: Settings) -> None:
    store = DynamoStaffStore(dynamodb_settings)
    # Fixture seeds demos; re-seed must stay idempotent.
    assert ensure_demo_staff_accounts(store, settings=dynamodb_settings) == 0
    assert store.get_by_username("admin") is not None
    assert store.get_by_username("staff") is not None

    principal = authenticate_staff_credentials(
        "admin",
        dynamodb_settings.demo_staff_password,
        staff_store=store,
    )
    assert principal.role == "administrator"
    token = issue_staff_access_token(principal, settings=dynamodb_settings)
    verified = verify_staff_access_token(
        token,
        settings=dynamodb_settings,
        staff_store=store,
    )
    assert verified.staff_id == principal.staff_id

    revoke_staff_sessions(principal.staff_id, staff_store=store)
    try:
        verify_staff_access_token(token, settings=dynamodb_settings, staff_store=store)
        raise AssertionError("expected revoked token")
    except Exception as exc:
        assert "revoked" in str(exc).lower() or "valid" in str(exc).lower()


def test_dynamo_username_claim_conflict(dynamodb_settings: Settings) -> None:
    from app.database.staff_store import StaffUsernameConflictError
    from app.schemas.staff_user import StoredStaffUser

    store = DynamoStaffStore(dynamodb_settings)
    ensure_demo_staff_accounts(store, settings=dynamodb_settings)
    duplicate = StoredStaffUser(
        staffId="staff_other",
        username="staff",
        name="Other",
        email="other@example.com",
        passwordHash=hash_password("x"),
        role="municipal_staff",
        municipalityId="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        departmentIds=["d1111111-1111-1111-1111-111111111111"],
        active=True,
        createdAt="2026-08-01T00:00:00Z",
        updatedAt="2026-08-01T00:00:00Z",
    )
    try:
        store.create(duplicate)
        raise AssertionError("expected conflict")
    except StaffUsernameConflictError:
        pass
