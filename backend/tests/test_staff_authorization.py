"""API authorization checks for staff actions (issue #72)."""

from __future__ import annotations

import time

import pytest

from app.config import get_settings
from app.core.staff_auth import issue_staff_access_token
from app.database.memory import ticket_store
from app.services.ai_job_queue import ai_job_queue
from tests.conftest import contribution_ready_auth_headers, issue_test_staff_token
from tests.test_submit_ticket import VALID_PAYLOAD

BEIRUT_MUNICIPALITY = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
OTHER_MUNICIPALITY = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ROAD_MAINTENANCE = "d1111111-1111-1111-1111-111111111111"
WASTE_MANAGEMENT = "d2222222-2222-2222-2222-222222222222"
STREET_LIGHTING = "d3333333-3333-3333-3333-333333333333"
MUNICIPAL_STAFF_ID = "staff_muni_001"


def _create_ticket(client) -> dict:
    response = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=contribution_ready_auth_headers(),
    )
    assert response.status_code == 201, response.text
    assert ai_job_queue.run_once().outcome == "succeeded"
    return response.json()


def _staff_headers(client, username: str) -> dict[str, str]:
    token = issue_test_staff_token(client, username=username)
    return {"Authorization": f"Bearer {token}"}


def _stamp_ticket_scope(
    ticket_id: str,
    *,
    municipality_id: str | None = BEIRUT_MUNICIPALITY,
    department_id: str | None = ROAD_MAINTENANCE,
    category: str = "road_damage",
) -> None:
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    ticket_store.save(
        stored.model_copy(
            update={
                "municipality_id": municipality_id,
                "department_id": department_id,
                "category": category,
                "ai_suggested_category": category,
            },
        )
    )


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
    assert body["staffId"]
    assert body["role"] in {"municipal_staff", "administrator"}
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


def test_municipal_staff_list_is_scoped_by_municipality_and_departments(
    anonymous_client,
    client,
):
    in_department = _create_ticket(client)
    unassigned = _create_ticket(client)
    other_department = _create_ticket(client)
    other_municipality = _create_ticket(client)
    _stamp_ticket_scope(in_department["ticketId"], department_id=ROAD_MAINTENANCE)
    _stamp_ticket_scope(unassigned["ticketId"], department_id=None)
    _stamp_ticket_scope(
        other_department["ticketId"],
        department_id=WASTE_MANAGEMENT,
        category="waste",
    )
    _stamp_ticket_scope(
        other_municipality["ticketId"],
        municipality_id=OTHER_MUNICIPALITY,
        department_id=ROAD_MAINTENANCE,
    )

    response = anonymous_client.get(
        "/v1/tickets",
        headers=_staff_headers(anonymous_client, "staff"),
    )

    assert response.status_code == 200
    visible_ids = {ticket["ticketId"] for ticket in response.json()}
    assert in_department["ticketId"] in visible_ids
    assert unassigned["ticketId"] in visible_ids
    assert other_department["ticketId"] not in visible_ids
    assert other_municipality["ticketId"] not in visible_ids


def test_municipal_staff_out_of_scope_detail_matches_missing_ticket(
    anonymous_client,
    client,
):
    created = _create_ticket(client)
    _stamp_ticket_scope(created["ticketId"], department_id=WASTE_MANAGEMENT, category="waste")
    headers = _staff_headers(anonymous_client, "staff")

    out_of_scope = anonymous_client.get(f"/v1/tickets/{created['ticketId']}", headers=headers)
    missing = anonymous_client.get("/v1/tickets/tkt_missing_id", headers=headers)

    assert out_of_scope.status_code == 404
    assert missing.status_code == 404
    assert out_of_scope.json()["error"]["code"] == missing.json()["error"]["code"]


def test_out_of_scope_ticket_returns_404_to_municipal_staff_and_200_to_admin(
    anonymous_client,
    client,
):
    created = _create_ticket(client)
    _stamp_ticket_scope(created["ticketId"], department_id=WASTE_MANAGEMENT, category="waste")

    municipal = anonymous_client.get(
        f"/v1/tickets/{created['ticketId']}", headers=_staff_headers(anonymous_client, "staff")
    )
    administrator = anonymous_client.get(
        f"/v1/tickets/{created['ticketId']}", headers=_staff_headers(anonymous_client, "admin")
    )

    assert municipal.status_code == 404
    assert municipal.json()["error"]["code"] == "TICKET_NOT_FOUND"
    assert administrator.status_code == 200
    assert administrator.json()["ticketId"] == created["ticketId"]


def test_municipal_staff_cannot_assign_unscoped_department(anonymous_client, client):
    created = _create_ticket(client)
    _stamp_ticket_scope(created["ticketId"], department_id=ROAD_MAINTENANCE)

    response = anonymous_client.patch(
        f"/v1/tickets/{created['ticketId']}/department",
        json={"departmentId": WASTE_MANAGEMENT, "updatedBy": "spoofed-actor"},
        headers=_staff_headers(anonymous_client, "staff"),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_category_review_cannot_auto_assign_unscoped_department(anonymous_client, client):
    created = _create_ticket(client)
    _stamp_ticket_scope(created["ticketId"], department_id=None)

    response = anonymous_client.patch(
        f"/v1/tickets/{created['ticketId']}/category",
        json={"finalCategory": "waste", "categoryReviewedBy": "spoofed-reviewer"},
        headers=_staff_headers(anonymous_client, "staff"),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.final_category is None
    assert stored.department_id is None


def test_staff_mutation_actor_identity_uses_verified_principal(anonymous_client, client):
    created = _create_ticket(client)
    _stamp_ticket_scope(created["ticketId"], department_id=ROAD_MAINTENANCE)
    headers = _staff_headers(anonymous_client, "staff")

    status_response = anonymous_client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "UNDER_REVIEW", "updatedBy": "spoofed-status"},
        headers=headers,
    )
    category_response = anonymous_client.patch(
        f"/v1/tickets/{created['ticketId']}/category",
        json={"finalCategory": "road_damage", "categoryReviewedBy": "spoofed-reviewer"},
        headers=headers,
    )
    department_response = anonymous_client.patch(
        f"/v1/tickets/{created['ticketId']}/department",
        json={"departmentId": STREET_LIGHTING, "updatedBy": "spoofed-department"},
        headers=headers,
    )

    assert status_response.status_code == 200
    assert status_response.json()["updatedBy"] == MUNICIPAL_STAFF_ID
    assert status_response.json()["statusHistory"][-1]["changedBy"] == MUNICIPAL_STAFF_ID
    assert category_response.status_code == 200
    assert category_response.json()["ai"]["categoryReviewedBy"] == MUNICIPAL_STAFF_ID
    assert department_response.status_code == 200
    assert department_response.json()["updatedBy"] == MUNICIPAL_STAFF_ID
    audit_actor_ids = {entry["actorId"] for entry in department_response.json()["auditHistory"]}
    assert audit_actor_ids == {MUNICIPAL_STAFF_ID}


def test_merge_actor_identity_uses_verified_principal(anonymous_client, client):
    main = _create_ticket(client)
    duplicate = _create_ticket(client)
    _stamp_ticket_scope(main["ticketId"], department_id=ROAD_MAINTENANCE)
    _stamp_ticket_scope(duplicate["ticketId"], department_id=ROAD_MAINTENANCE)

    response = anonymous_client.post(
        "/v1/tickets/merge",
        json={
            "canonicalTicketId": main["ticketId"],
            "duplicateTicketIds": [duplicate["ticketId"]],
            "mergedBy": "spoofed-merge",
        },
        headers=_staff_headers(anonymous_client, "staff"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["updatedBy"] == MUNICIPAL_STAFF_ID
    audits = [entry for entry in body["auditHistory"] if entry["actionType"] == "DUPLICATE_MERGE"]
    assert len(audits) == 1
    assert audits[0]["actorId"] == MUNICIPAL_STAFF_ID


def test_citizen_token_cannot_access_staff_routes(
    anonymous_client,
    contribution_ready_citizen_headers,
):
    response = anonymous_client.get("/v1/tickets", headers=contribution_ready_citizen_headers)

    _assert_unauthorized(response)


def test_admin_dependency_rejects_regular_staff():
    from fastapi import HTTPException

    from app.core.staff_auth import principal_from_user, require_admin
    from app.database.memory_staff import staff_store

    class RequestStub:
        state = type("State", (), {"request_id": "req_test"})()

    staff = staff_store.get_by_username("staff")
    admin = staff_store.get_by_username("admin")
    assert staff is not None
    assert admin is not None

    with pytest.raises(HTTPException) as exc_info:
        require_admin(RequestStub(), principal_from_user(staff))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "FORBIDDEN"
    assert require_admin(RequestStub(), principal_from_user(admin)).staff_id == "staff_admin_001"


def test_citizen_submit_requires_contribution_ready_auth(anonymous_client):
    response = anonymous_client.post("/v1/tickets", json=VALID_PAYLOAD)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.headers.get("WWW-Authenticate", "").startswith("Bearer")


def test_citizen_tracking_lookup_remains_public(anonymous_client):
    created = _create_ticket(anonymous_client)

    response = anonymous_client.get(f"/v1/tickets/track/{created['trackingCode']}")

    assert response.status_code == 200
    body = response.json()
    assert body["trackingCode"] == created["trackingCode"]
    assert "contact" not in body
    assert "ticketId" not in body
    assert "ownerUserId" not in body


def test_invalid_bearer_token_is_rejected(anonymous_client):
    response = anonymous_client.get(
        "/v1/tickets",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    _assert_unauthorized(response)


def test_expired_bearer_token_is_rejected(anonymous_client):
    from app.core.staff_auth import principal_from_user
    from app.database.memory_staff import staff_store

    settings = get_settings()
    user = staff_store.get_by_username("staff")
    assert user is not None
    # Issue a token that already expired one hour ago.
    token = issue_staff_access_token(
        principal_from_user(user),
        settings=settings,
        now=int(time.time()) - settings.staff_token_ttl_seconds - 3600,
    )

    response = anonymous_client.get(
        "/v1/tickets",
        headers={"Authorization": f"Bearer {token}"},
    )

    _assert_unauthorized(response)


def test_department_assignment_auth_integration_point_is_documented():
    """#141 mounts department assignment behind StaffActorDep / require_staff."""
    from app.api.deps import StaffActorDep, require_staff
    from app.core.staff_auth import StaffDep
    from app.core.staff_auth import require_staff as core_require_staff

    assert callable(require_staff)
    assert require_staff is core_require_staff
    assert StaffActorDep is StaffDep
