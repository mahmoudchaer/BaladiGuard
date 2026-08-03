"""Sprint 5 end-to-end API workflow coverage (issue #145).

This test intentionally exercises the configured in-memory path used by CI. The
same feature areas keep focused DynamoDB tests nearby; deployed-environment E2E
coverage is out of scope here because it needs real credentials and endpoints.
"""

from app.database.memory import ticket_store
from app.services.notifications.adapters import MockNotificationAdapter
from tests.conftest import contribution_ready_auth_headers
from tests.test_submit_ticket import EXPECTED_CONTACT, VALID_PAYLOAD

STREET_LIGHTING = "d3333333-3333-3333-3333-333333333333"
WASTE_MANAGEMENT = "d2222222-2222-2222-2222-222222222222"
ADMIN_STAFF_ID = "staff_admin_001"

PUBLIC_FORBIDDEN_FIELDS = {
    "ticketId",
    "ownerUserId",
    "contact",
    "imageReferences",
    "imageObjectKey",
    "department",
    "departmentId",
    "createdBy",
    "municipalityId",
    "duplicateGroupId",
    "updatedBy",
    "ai",
    "statusHistory",
    "auditHistory",
    "duplicateGroup",
    "duplicateSuggestions",
}


def _submit_report(anonymous_client, description: str = VALID_PAYLOAD["description"]) -> dict:
    response = anonymous_client.post(
        "/v1/tickets",
        json={**VALID_PAYLOAD, "description": description},
        headers=contribution_ready_auth_headers(),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["ticketId"].startswith("tkt_")
    assert body["ticketNumber"].startswith("BG-")
    assert len(body["trackingCode"]) == 6
    assert body["status"] == "SUBMITTED"
    return body


def _assert_unauthorized(response) -> None:
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    serialized = str(body).lower()
    assert "tkt_" not in serialized
    assert VALID_PAYLOAD["description"].lower() not in serialized


def test_sprint5_memory_workflow_exercises_citizen_and_staff_paths(
    anonymous_client,
    monkeypatch,
):
    delivered_notifications = []
    original_deliver = MockNotificationAdapter.deliver

    def capture_delivery(self, message, recipient=None):
        delivered_notifications.append((message, recipient))
        return original_deliver(self, message, recipient)

    monkeypatch.setattr(MockNotificationAdapter, "deliver", capture_delivery)

    created = _submit_report(anonymous_client)
    ticket_id = created["ticketId"]

    stored = ticket_store.get(ticket_id)
    assert stored is not None
    assert stored.tracking_code == created["trackingCode"]
    assert stored.priority is not None

    public_before_review = anonymous_client.get(f"/v1/tickets/track/{created['trackingCode']}")
    assert public_before_review.status_code == 200
    public_body = public_before_review.json()
    assert public_body["trackingCode"] == created["trackingCode"]
    assert public_body["ticketNumber"] == created["ticketNumber"]
    assert public_body["status"] == "SUBMITTED"
    assert public_body["category"] is None
    assert [entry["status"] for entry in public_body["timeline"]] == ["SUBMITTED"]
    assert PUBLIC_FORBIDDEN_FIELDS.isdisjoint(public_body)
    assert "ai" not in public_body
    assert "contact" not in public_body
    assert EXPECTED_CONTACT["phone"] not in str(public_body)

    _assert_unauthorized(anonymous_client.get("/v1/tickets"))
    _assert_unauthorized(anonymous_client.get(f"/v1/tickets/{ticket_id}"))
    _assert_unauthorized(
        anonymous_client.patch(
            f"/v1/tickets/{ticket_id}/status",
            json={"status": "UNDER_REVIEW", "updatedBy": "anonymous"},
        )
    )
    _assert_unauthorized(
        anonymous_client.patch(
            f"/v1/tickets/{ticket_id}/category",
            json={"finalCategory": "road_damage", "categoryReviewedBy": "anonymous"},
        )
    )
    _assert_unauthorized(
        anonymous_client.patch(
            f"/v1/tickets/{ticket_id}/department",
            json={"departmentId": STREET_LIGHTING, "updatedBy": "anonymous"},
        )
    )

    login = anonymous_client.post(
        "/v1/staff/login",
        json={"username": "admin", "password": "staff-demo-password"},
    )
    assert login.status_code == 200, login.text
    staff_headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    dashboard = anonymous_client.get("/v1/tickets", headers=staff_headers)
    assert dashboard.status_code == 200
    assert any(ticket["ticketId"] == ticket_id for ticket in dashboard.json())

    detail = anonymous_client.get(f"/v1/tickets/{ticket_id}", headers=staff_headers)
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["contact"]["phone"] == EXPECTED_CONTACT["phone"]
    assert detail_body["statusHistory"][0]["status"] == "SUBMITTED"
    assert detail_body["auditHistory"] == []

    under_review = anonymous_client.patch(
        f"/v1/tickets/{ticket_id}/status",
        headers=staff_headers,
        json={
            "status": "UNDER_REVIEW",
            "updatedBy": "staff-workflow",
            "note": "Queued for Sprint 5 workflow test.",
        },
    )
    assert under_review.status_code == 200, under_review.text
    assert under_review.json()["status"] == "UNDER_REVIEW"

    reviewed = anonymous_client.patch(
        f"/v1/tickets/{ticket_id}/category",
        headers=staff_headers,
        json={"finalCategory": "road_damage", "categoryReviewedBy": "staff-workflow"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["category"] == "road_damage"

    assigned_department = anonymous_client.patch(
        f"/v1/tickets/{ticket_id}/department",
        headers=staff_headers,
        json={"departmentId": STREET_LIGHTING, "updatedBy": "staff-workflow"},
    )
    assert assigned_department.status_code == 200, assigned_department.text
    assert assigned_department.json()["departmentId"] == STREET_LIGHTING
    assert assigned_department.json()["department"]["name"] == "Street Lighting"

    assigned_status = anonymous_client.patch(
        f"/v1/tickets/{ticket_id}/status",
        headers=staff_headers,
        json={
            "status": "ASSIGNED",
            "updatedBy": "staff-workflow",
            "note": "Assigned to the selected department.",
        },
    )
    assert assigned_status.status_code == 200, assigned_status.text

    final_detail = anonymous_client.get(f"/v1/tickets/{ticket_id}", headers=staff_headers)
    assert final_detail.status_code == 200
    final_body = final_detail.json()
    assert final_body["status"] == "ASSIGNED"
    assert final_body["category"] == "road_damage"
    assert final_body["departmentId"] == STREET_LIGHTING
    assert final_body["updatedBy"] == ADMIN_STAFF_ID
    assert [entry["status"] for entry in final_body["statusHistory"]] == [
        "SUBMITTED",
        "UNDER_REVIEW",
        "ASSIGNED",
    ]

    audit_action_types = [entry["actionType"] for entry in final_body["auditHistory"]]
    assert audit_action_types == [
        "STATUS_CHANGE",
        "CATEGORY_REVIEW",
        "DEPARTMENT_ASSIGN",
        "STATUS_CHANGE",
    ]
    status_audits = [
        entry for entry in final_body["auditHistory"] if entry["actionType"] == "STATUS_CHANGE"
    ]
    assert [(entry["previousValue"], entry["newValue"]) for entry in status_audits] == [
        ("SUBMITTED", "UNDER_REVIEW"),
        ("UNDER_REVIEW", "ASSIGNED"),
    ]
    audits_by_type = {entry["actionType"]: entry for entry in final_body["auditHistory"]}
    assert audits_by_type["CATEGORY_REVIEW"]["newValue"] == "road_damage"
    assert audits_by_type["DEPARTMENT_ASSIGN"]["newValue"] == STREET_LIGHTING

    stored_after_staff_work = ticket_store.get(ticket_id)
    assert stored_after_staff_work is not None
    assert stored_after_staff_work.status == "ASSIGNED"
    assert stored_after_staff_work.final_category == "road_damage"
    assert stored_after_staff_work.department_id == STREET_LIGHTING

    decoy = _submit_report(
        anonymous_client,
        "Overflowing bins outside the market should route somewhere else.",
    )
    decoy_review = anonymous_client.patch(
        f"/v1/tickets/{decoy['ticketId']}/category",
        headers=staff_headers,
        json={"finalCategory": "waste", "categoryReviewedBy": "staff-workflow"},
    )
    assert decoy_review.status_code == 200
    decoy_department = anonymous_client.patch(
        f"/v1/tickets/{decoy['ticketId']}/department",
        headers=staff_headers,
        json={"departmentId": WASTE_MANAGEMENT, "updatedBy": "staff-workflow"},
    )
    assert decoy_department.status_code == 200

    filtered = anonymous_client.get(
        "/v1/tickets",
        headers=staff_headers,
        params={
            "status": "ASSIGNED",
            "category": "road_damage",
            "urgency": stored_after_staff_work.priority,
            "departmentId": STREET_LIGHTING,
        },
    )
    assert filtered.status_code == 200
    assert [ticket["ticketId"] for ticket in filtered.json()] == [ticket_id]

    public_after_staff_work = anonymous_client.get(f"/v1/tickets/track/{created['trackingCode']}")
    assert public_after_staff_work.status_code == 200
    public_after_body = public_after_staff_work.json()
    assert public_after_body["status"] == "ASSIGNED"
    assert public_after_body["category"] == "road_damage"
    assert [entry["status"] for entry in public_after_body["timeline"]] == [
        "SUBMITTED",
        "UNDER_REVIEW",
        "ASSIGNED",
    ]
    assert PUBLIC_FORBIDDEN_FIELDS.isdisjoint(public_after_body)
    assert "ai" not in public_after_body
    assert "contact" not in public_after_body
    assert EXPECTED_CONTACT["phone"] not in str(public_after_body)

    target_notifications = [
        (message.event, message.status, recipient)
        for message, recipient in delivered_notifications
        if message.ticket_id == ticket_id
    ]
    assert [event for event, _status, _recipient in target_notifications] == [
        "ticket_created",
        "ticket_updated",
        "ticket_updated",
    ]
    assert [status for _event, status, _recipient in target_notifications] == [
        "SUBMITTED",
        "UNDER_REVIEW",
        "ASSIGNED",
    ]
    assert all(recipient is not None for _event, _status, recipient in target_notifications)
    assert all(
        recipient.phone == EXPECTED_CONTACT["phone"]
        for _event, _status, recipient in target_notifications
    )
