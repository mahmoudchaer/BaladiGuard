"""Administrator HTTP staff-account management coverage (issue #236)."""

from __future__ import annotations

from app.database.memory_account_audit import account_audit_store
from tests.conftest import issue_test_staff_token


def _headers(client, username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username=username)}"}


def _create_payload(username: str = "api.new.staff") -> dict:
    return {
        "username": username,
        "name": "API New Staff",
        "email": f"{username}@example.com",
        "password": "safe-admin-created-password",
        "role": "municipal_staff",
        "municipalityId": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "departmentIds": ["d1111111-1111-1111-1111-111111111111"],
    }


def _assert_no_secrets(body: object) -> None:
    rendered = str(body).lower()
    for forbidden in (
        "passwordhash",
        "password_hash",
        "sessionepoch",
        "session_epoch",
        "reset",
        "token",
    ):
        assert forbidden not in rendered


def test_admin_can_create_list_read_update_and_toggle_staff_accounts(anonymous_client):
    admin_headers = _headers(anonymous_client, "admin")
    created = anonymous_client.post(
        "/v1/admin/staff-accounts", json=_create_payload(), headers=admin_headers
    )
    assert created.status_code == 201, created.text
    account = created.json()
    _assert_no_secrets(account)
    assert account["active"] is True
    assert account["username"] == "api.new.staff"
    staff_id = account["staffId"]

    listed = anonymous_client.get("/v1/admin/staff-accounts", headers=admin_headers)
    assert listed.status_code == 200
    assert staff_id in {item["staffId"] for item in listed.json()}
    _assert_no_secrets(listed.json())

    read = anonymous_client.get(f"/v1/admin/staff-accounts/{staff_id}", headers=admin_headers)
    assert read.status_code == 200
    assert read.json() == account

    scoped = anonymous_client.patch(
        f"/v1/admin/staff-accounts/{staff_id}",
        json={
            "municipalityId": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "departmentIds": ["d3333333-3333-3333-3333-333333333333"],
        },
        headers=admin_headers,
    )
    assert scoped.status_code == 200, scoped.text
    assert scoped.json()["departmentIds"] == ["d3333333-3333-3333-3333-333333333333"]

    deactivated = anonymous_client.post(
        f"/v1/admin/staff-accounts/{staff_id}/deactivate", headers=admin_headers
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["active"] is False
    login = anonymous_client.post(
        "/v1/staff/login",
        json={"username": "api.new.staff", "password": "safe-admin-created-password"},
    )
    assert login.status_code == 401

    reactivated = anonymous_client.post(
        f"/v1/admin/staff-accounts/{staff_id}/reactivate", headers=admin_headers
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["active"] is True
    assert (
        anonymous_client.post(
            "/v1/staff/login",
            json={"username": "api.new.staff", "password": "safe-admin-created-password"},
        ).status_code
        == 200
    )

    actions = [entry.action_type for entry in account_audit_store.list_by_target_staff_id(staff_id)]
    assert actions == [
        "STAFF_CREATED",
        "STAFF_SCOPE_CHANGED",
        "STAFF_DEACTIVATED",
        "STAFF_REACTIVATED",
    ]


def test_admin_update_validates_role_scope_and_duplicate_accounts(anonymous_client):
    headers = _headers(anonymous_client, "admin")
    created = anonymous_client.post(
        "/v1/admin/staff-accounts", json=_create_payload("api.duplicate"), headers=headers
    )
    assert created.status_code == 201
    staff_id = created.json()["staffId"]

    duplicate = anonymous_client.post(
        "/v1/admin/staff-accounts", json=_create_payload("api.duplicate"), headers=headers
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "STAFF_USERNAME_CONFLICT"

    invalid_scope = anonymous_client.patch(
        f"/v1/admin/staff-accounts/{staff_id}",
        json={"role": "municipal_staff", "municipalityId": None, "departmentIds": []},
        headers=headers,
    )
    assert invalid_scope.status_code == 400
    assert invalid_scope.json()["error"]["code"] == "VALIDATION_ERROR"

    global_admin = anonymous_client.patch(
        f"/v1/admin/staff-accounts/{staff_id}", json={"role": "administrator"}, headers=headers
    )
    assert global_admin.status_code == 200
    assert global_admin.json()["municipalityId"] is None
    assert global_admin.json()["departmentIds"] is None


def test_admin_routes_are_safe_for_guests_invalid_sessions_and_municipal_staff(anonymous_client):
    route = "/v1/admin/staff-accounts"
    assert anonymous_client.get(route).status_code == 401
    assert (
        anonymous_client.get(route, headers={"Authorization": "Bearer invalid"}).status_code == 401
    )
    municipal = anonymous_client.get(route, headers=_headers(anonymous_client, "staff"))
    assert municipal.status_code == 403
    assert municipal.json()["error"]["code"] == "FORBIDDEN"
