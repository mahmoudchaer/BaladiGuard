"""Account audit + verified actor hardening (issue #181)."""

from __future__ import annotations

import json

import pytest

from app.core.staff_auth import principal_from_user
from app.database.memory_account_audit import account_audit_store
from app.database.memory_staff import staff_store
from app.services.audit.safe_values import (
    contains_forbidden_audit_key,
    safe_audit_value,
    staff_snapshot_for_audit,
)
from app.services.staff.account_audit import account_audit_service
from app.services.staff.admin_accounts import (
    StaffAccountAdminError,
    staff_account_admin_service,
)
from app.services.staff.bootstrap import BEIRUT_MUNICIPALITY_ID, ROAD_MAINTENANCE_DEPT
from app.services.staff.password_reset import staff_password_reset_service
from tests.test_read_tickets import create_ticket

ADMIN_STAFF_ID = "staff_admin_001"
MUNICIPAL_STAFF_ID = "staff_muni_001"
STREET_LIGHTING = "d3333333-3333-3333-3333-333333333333"


def _admin_principal():
    user = staff_store.get(ADMIN_STAFF_ID)
    assert user is not None
    return principal_from_user(user)


def _municipal_principal():
    user = staff_store.get(MUNICIPAL_STAFF_ID)
    assert user is not None
    return principal_from_user(user)


def test_ticket_mutations_record_verified_actor_role(client, staff_auth_headers):
    created = create_ticket(client)

    status = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        headers=staff_auth_headers,
        json={"status": "UNDER_REVIEW", "updatedBy": "spoofed-actor"},
    )
    assert status.status_code == 200
    audits = status.json()["auditHistory"]
    status_audit = next(item for item in audits if item["actionType"] == "STATUS_CHANGE")
    assert status_audit["actorId"] == MUNICIPAL_STAFF_ID
    assert status_audit["actorRole"] == "municipal_staff"
    assert status_audit["actorId"] != "spoofed-actor"


def test_service_ignores_payload_actor_when_principal_present(client, staff_auth_headers):
    created = create_ticket(client)
    from app.schemas.ticket_response import UpdateTicketStatusRequest
    from app.services.complaints.ticket_service import ticket_service

    principal = _municipal_principal()
    response = ticket_service.update_ticket_status(
        created["ticketId"],
        UpdateTicketStatusRequest(status="UNDER_REVIEW", updatedBy="client-spoof"),
        staff_principal=principal,
    )
    audit = next(item for item in response.audit_history if item.action_type == "STATUS_CHANGE")
    assert audit.actor_id == MUNICIPAL_STAFF_ID
    assert audit.actor_role == "municipal_staff"


def test_admin_account_actions_are_audited():
    actor = _admin_principal()
    created = staff_account_admin_service.create_staff(
        actor,
        username="audit.staff",
        name="Audit Staff",
        email="audit.staff@example.com",
        password="staff-demo-password",
        role="municipal_staff",
        municipality_id=BEIRUT_MUNICIPALITY_ID,
        department_ids=[ROAD_MAINTENANCE_DEPT],
    )

    role_changed = staff_account_admin_service.change_role(
        actor,
        staff_id=created.staff_id,
        role="municipal_staff",
        municipality_id=BEIRUT_MUNICIPALITY_ID,
        department_ids=[ROAD_MAINTENANCE_DEPT, STREET_LIGHTING],
    )
    scoped = staff_account_admin_service.change_scope(
        actor,
        staff_id=role_changed.staff_id,
        municipality_id=BEIRUT_MUNICIPALITY_ID,
        department_ids=[STREET_LIGHTING],
    )
    deactivated = staff_account_admin_service.set_active(
        actor,
        staff_id=scoped.staff_id,
        active=False,
    )

    entries = account_audit_store.list_by_target_staff_id(created.staff_id)
    action_types = [entry.action_type for entry in entries]
    assert "STAFF_CREATED" in action_types
    assert "STAFF_ROLE_CHANGED" in action_types
    assert "STAFF_SCOPE_CHANGED" in action_types
    assert "STAFF_DEACTIVATED" in action_types
    assert deactivated.active is False

    for entry in entries:
        assert entry.actor_id == ADMIN_STAFF_ID
        assert entry.actor_role == "administrator"
        payload = f"{entry.summary} {entry.previous_value} {entry.new_value}".lower()
        assert "password" not in payload
        assert "hash" not in payload
        assert "token" not in payload
        assert "code" not in payload


def test_non_admin_cannot_manage_staff_accounts():
    actor = _municipal_principal()
    try:
        staff_account_admin_service.create_staff(
            actor,
            username="blocked.staff",
            name="Blocked",
            email="blocked@example.com",
            password="staff-demo-password",
            role="municipal_staff",
            municipality_id=BEIRUT_MUNICIPALITY_ID,
            department_ids=[ROAD_MAINTENANCE_DEPT],
        )
        raise AssertionError("expected StaffAccountAdminError")
    except StaffAccountAdminError as exc:
        assert "administrators" in exc.message.lower()


def test_password_reset_and_logout_write_account_audit(anonymous_client):
    message, challenge_id = staff_password_reset_service.request_reset("staff")
    assert challenge_id is not None
    code = staff_password_reset_service.peek_dev_reset_code(challenge_id)
    assert code is not None
    assert message

    confirm = staff_password_reset_service.confirm_reset(
        username="staff",
        code=code,
        new_password="staff-demo-password",
    )
    assert "Password updated" in confirm

    reset_entries = [
        entry
        for entry in account_audit_store.list_by_target_staff_id(MUNICIPAL_STAFF_ID)
        if entry.action_type == "STAFF_PASSWORD_RESET_COMPLETED"
    ]
    assert len(reset_entries) == 1
    assert reset_entries[0].previous_value is None
    assert reset_entries[0].new_value is None
    assert "password" not in reset_entries[0].summary.lower()
    assert "code" not in reset_entries[0].summary.lower()
    assert "hash" not in reset_entries[0].summary.lower()
    assert "token" not in reset_entries[0].summary.lower()

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
    revoke_entries = [
        entry
        for entry in account_audit_store.list_by_target_staff_id(MUNICIPAL_STAFF_ID)
        if entry.action_type == "STAFF_SESSION_REVOKED"
    ]
    assert revoke_entries


def test_account_audit_write_failure_does_not_block_primary_action(monkeypatch):
    actor = _admin_principal()

    def boom(*_args, **_kwargs):
        raise RuntimeError("account audit unavailable")

    monkeypatch.setattr(account_audit_service._resolved_store(), "append", boom)

    created = staff_account_admin_service.create_staff(
        actor,
        username="audit.fail",
        name="Fail Staff",
        email="audit.fail@example.com",
        password="staff-demo-password",
        role="municipal_staff",
        municipality_id=BEIRUT_MUNICIPALITY_ID,
        department_ids=[ROAD_MAINTENANCE_DEPT],
    )
    assert staff_store.get(created.staff_id) is not None


def test_safe_audit_value_excludes_sensitive_fields():
    snapshot = staff_snapshot_for_audit(
        staff_id="staff_x",
        username="x",
        name="X",
        role="municipal_staff",
        municipality_id=BEIRUT_MUNICIPALITY_ID,
        department_ids=[ROAD_MAINTENANCE_DEPT],
        active=True,
    )
    snapshot["passwordHash"] = "should-not-persist"
    snapshot["resetCode"] = "123456"
    sanitized = json.loads(safe_audit_value(snapshot) or "{}")
    assert "passwordHash" not in sanitized
    assert "resetCode" not in sanitized
    assert sanitized["username"] == "x"
    assert not contains_forbidden_audit_key(sanitized)


def test_safe_audit_value_rejects_sensitive_string_payloads():
    with pytest.raises(ValueError, match="forbidden sensitive material"):
        safe_audit_value("passwordHash=secret token=abc")

    with pytest.raises(ValueError, match="forbidden sensitive material"):
        safe_audit_value("reset_code=123456")

    # JSON object strings are sanitized like mappings (sensitive keys dropped).
    sanitized = json.loads(safe_audit_value('{"username":"x","passwordHash":"nope"}') or "{}")
    assert sanitized == {"username": "x"}
    assert safe_audit_value("UNDER_REVIEW") == "UNDER_REVIEW"
