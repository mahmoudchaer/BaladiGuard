"""Maintenance work-order workflow and structured outcome reasons (issue #247)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.database.dynamodb_tables import TABLE_DEFINITIONS
from app.database.memory import ticket_store
from app.database.memory_audit_history import audit_history_store
from app.services.ai_job_queue import ai_job_queue
from app.services.work_orders.reasons import (
    CLOSURE_REASON_CODES,
    REJECTION_REASON_CODES,
    RESOLUTION_REASON_CODES,
    citizen_safe_message,
    required_outcome_kind,
)
from app.services.work_orders.transitions import ticket_status_path
from app.services.uploads.photo_upload_service import photo_upload_service
from tests.conftest import contribution_ready_auth_headers, issue_test_staff_token
from tests.test_submit_ticket import VALID_PAYLOAD
from tests.test_upload_report_photo import FakeS3Client, image_bytes, set_aws_env
from tests.test_workforce import BEIRUT, OTHER_MUNICIPALITY, ROAD, WASTE

ADMIN_STAFF_ID = "staff_admin_001"


def _admin(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username='admin')}"}


def _staff(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username='staff')}"}


def _create_ticket(client: TestClient) -> dict:
    response = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=contribution_ready_auth_headers(),
    )
    assert response.status_code == 201, response.text
    assert ai_job_queue.run_once().outcome == "succeeded"
    return response.json()


def _accept_ticket(client: TestClient, ticket_id: str, *, status: str = "UNDER_REVIEW") -> None:
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    ticket_store.save(
        stored.model_copy(
            update={
                "municipality_id": BEIRUT,
                "department_id": ROAD,
                "status": status,
            }
        )
    )


def _create_worker(client: TestClient, *, departments: list[str] | None = None) -> dict:
    response = client.post(
        "/v1/workforce/workers",
        json={
            "municipalityId": BEIRUT,
            "displayName": "Road crew A",
            "departmentIds": departments or [ROAD],
        },
        headers=_admin(client),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _attach_after_image(client: TestClient, work_order_id: str, monkeypatch) -> None:
    fake = FakeS3Client()
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", fake)
    response = client.post(
        f"/v1/work-orders/{work_order_id}/evidence",
        params={"kind": "AFTER"},
        files={"file": ("after.png", image_bytes(), "image/png")},
        headers=_staff(client),
    )
    assert response.status_code == 200, response.text


def _advance_to_in_progress(client: TestClient, ticket_id: str) -> None:
    _accept_ticket(client, ticket_id, status="UNDER_REVIEW")
    assert (
        client.patch(
            f"/v1/tickets/{ticket_id}/status",
            json={"status": "ASSIGNED"},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/v1/tickets/{ticket_id}/status",
            json={"status": "IN_PROGRESS"},
        ).status_code
        == 200
    )


def test_work_order_table_is_defined() -> None:
    assert "work-orders" in {item["suffix"] for item in TABLE_DEFINITIONS}


def test_ticket_status_path_never_skips_allowed_transitions() -> None:
    assert ticket_status_path("UNDER_REVIEW", "IN_PROGRESS") == ["ASSIGNED", "IN_PROGRESS"]
    assert ticket_status_path("ASSIGNED", "IN_PROGRESS") == ["IN_PROGRESS"]
    assert ticket_status_path("IN_PROGRESS", "IN_PROGRESS") == []
    assert ticket_status_path("CLOSED", "IN_PROGRESS") is None


def test_anonymous_work_order_routes_are_unauthorized(anonymous_client: TestClient) -> None:
    assert anonymous_client.post("/v1/tickets/tkt_missing/work-orders", json={}).status_code == 401
    assert anonymous_client.get("/v1/work-orders/wo_missing").status_code == 401


def test_create_work_order_from_submitted_is_rejected(client: TestClient) -> None:
    created = _create_ticket(client)
    response = client.post(f"/v1/tickets/{created['ticketId']}/work-orders", json={})
    assert response.status_code == 400
    assert "accepted ticket" in response.json()["error"]["message"]


def test_create_work_order_requires_department(client: TestClient) -> None:
    created = _create_ticket(client)
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    ticket_store.save(
        stored.model_copy(
            update={"status": "UNDER_REVIEW", "municipality_id": BEIRUT, "department_id": None}
        )
    )
    response = client.post(f"/v1/tickets/{created['ticketId']}/work-orders", json={})
    assert response.status_code == 400
    assert "department" in response.json()["error"]["message"]


def test_create_work_order_is_idempotent_and_syncs_ticket(client: TestClient) -> None:
    created = _create_ticket(client)
    _accept_ticket(client, created["ticketId"])

    first = client.post(
        f"/v1/tickets/{created['ticketId']}/work-orders",
        json={"summary": "Repair the pothole"},
    )
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["workOrderId"].startswith("wo_")
    assert body["ticketId"] == created["ticketId"]
    assert body["state"] == "QUEUED"
    assert body["summary"] == "Repair the pothole"
    assert body["created"] is True
    assert body["createdBy"] == ADMIN_STAFF_ID
    assert body["ticketStatus"] == "ASSIGNED"

    second = client.post(
        f"/v1/tickets/{created['ticketId']}/work-orders",
        json={"summary": "Different summary on retry"},
    )
    assert second.status_code == 200
    assert second.json()["workOrderId"] == body["workOrderId"]
    assert second.json()["created"] is False
    assert second.json()["summary"] == "Repair the pothole"

    listed = client.get(f"/v1/tickets/{created['ticketId']}/work-orders")
    assert listed.status_code == 200
    assert listed.json()["activeWorkOrderId"] == body["workOrderId"]
    assert len(listed.json()["items"]) == 1

    ticket = client.get(f"/v1/tickets/{created['ticketId']}").json()
    assert ticket["status"] == "ASSIGNED"
    assert ticket["activeWorkOrderId"] == body["workOrderId"]
    assert any(entry["actionType"] == "WORK_ORDER_CREATE" for entry in ticket["auditHistory"])


def test_concurrent_create_yields_one_active_work_order(client: TestClient) -> None:
    created = _create_ticket(client)
    _accept_ticket(client, created["ticketId"])

    def _create() -> str:
        response = client.post(f"/v1/tickets/{created['ticketId']}/work-orders", json={})
        assert response.status_code in {200, 201}, response.text
        return response.json()["workOrderId"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _: _create(), range(8)))

    assert len(set(ids)) == 1
    listed = client.get(f"/v1/tickets/{created['ticketId']}/work-orders").json()
    active = [
        item for item in listed["items"] if item["state"] in {"QUEUED", "ASSIGNED", "IN_PROGRESS"}
    ]
    assert len(active) == 1


def test_work_order_assignment_uses_workforce_scope(client: TestClient) -> None:
    created = _create_ticket(client)
    _accept_ticket(client, created["ticketId"])
    worker = _create_worker(client)
    inactive = _create_worker(client)
    client.post(
        f"/v1/workforce/workers/{inactive['workerId']}/deactivate",
        headers=_admin(client),
    )
    other = client.post(
        "/v1/workforce/workers",
        json={
            "municipalityId": OTHER_MUNICIPALITY,
            "displayName": "Other city crew",
            "departmentIds": [ROAD],
        },
        headers=_admin(client),
    ).json()
    waste_only = _create_worker(client, departments=[WASTE])

    created_wo = client.post(
        f"/v1/tickets/{created['ticketId']}/work-orders",
        json={"workerId": worker["workerId"]},
    )
    assert created_wo.status_code == 201, created_wo.text
    assert created_wo.json()["state"] == "ASSIGNED"
    assert created_wo.json()["assignedWorkerId"] == worker["workerId"]
    ticket = client.get(f"/v1/tickets/{created['ticketId']}").json()
    assert ticket["assignedWorkerId"] == worker["workerId"]

    work_order_id = created_wo.json()["workOrderId"]
    assert (
        client.post(
            f"/v1/work-orders/{work_order_id}/assign",
            json={"workerId": inactive["workerId"]},
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/v1/work-orders/{work_order_id}/assign",
            json={"workerId": other["workerId"]},
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/v1/work-orders/{work_order_id}/assign",
            json={"workerId": waste_only["workerId"]},
        ).status_code
        == 400
    )


def test_start_complete_cancel_and_ticket_sync(client: TestClient, monkeypatch) -> None:
    created = _create_ticket(client)
    _accept_ticket(client, created["ticketId"])
    worker = _create_worker(client)
    work_order = client.post(
        f"/v1/tickets/{created['ticketId']}/work-orders",
        json={"workerId": worker["workerId"]},
    ).json()

    started = client.post(f"/v1/work-orders/{work_order['workOrderId']}/start")
    assert started.status_code == 200, started.text
    assert started.json()["state"] == "IN_PROGRESS"
    assert started.json()["ticketStatus"] == "IN_PROGRESS"
    assert client.get(f"/v1/tickets/{created['ticketId']}").json()["status"] == "IN_PROGRESS"

    blocked = client.post(
        f"/v1/work-orders/{work_order['workOrderId']}/complete",
        json={"note": "Crew finished the patch."},
    )
    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "COMPLETION_EVIDENCE_REQUIRED"
    _attach_after_image(client, work_order["workOrderId"], monkeypatch)

    completed = client.post(
        f"/v1/work-orders/{work_order['workOrderId']}/complete",
        json={"note": "Crew finished the patch."},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["state"] == "COMPLETED"
    assert completed.json()["completionNote"] == "Crew finished the patch."
    ticket = client.get(f"/v1/tickets/{created['ticketId']}").json()
    assert ticket["status"] == "IN_PROGRESS"
    assert ticket["activeWorkOrderId"] is None
    assert ticket["outcome"] is None

    assert (
        client.post(
            f"/v1/work-orders/{work_order['workOrderId']}/complete",
            json={},
        ).status_code
        == 400
    )

    replacement = client.post(f"/v1/tickets/{created['ticketId']}/work-orders", json={})
    assert replacement.status_code == 201
    cancelled = client.post(
        f"/v1/work-orders/{replacement.json()['workOrderId']}/cancel",
        json={"reasonCode": "NO_LONGER_NEEDED", "note": "Weather window closed."},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "CANCELLED"
    assert cancelled.json()["cancelReasonCode"] == "NO_LONGER_NEEDED"
    assert client.get(f"/v1/tickets/{created['ticketId']}").json()["status"] == "IN_PROGRESS"


def test_start_without_assignee_is_rejected(client: TestClient) -> None:
    created = _create_ticket(client)
    _accept_ticket(client, created["ticketId"])
    work_order = client.post(f"/v1/tickets/{created['ticketId']}/work-orders", json={}).json()
    response = client.post(f"/v1/work-orders/{work_order['workOrderId']}/start")
    assert response.status_code == 400
    assert "Assign a worker or team" in response.json()["error"]["message"]


def test_out_of_scope_staff_cannot_read_work_order(client: TestClient) -> None:
    created = _create_ticket(client)
    _accept_ticket(client, created["ticketId"])
    work_order = client.post(f"/v1/tickets/{created['ticketId']}/work-orders", json={}).json()
    staff = _staff(client)
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    ticket_store.save(stored.model_copy(update={"municipality_id": OTHER_MUNICIPALITY}))
    response = client.get(f"/v1/work-orders/{work_order['workOrderId']}", headers=staff)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_resolve_requires_resolution_reason(client: TestClient) -> None:
    created = _create_ticket(client)
    _advance_to_in_progress(client, created["ticketId"])

    missing = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "RESOLVED"},
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "OUTCOME_REASON_REQUIRED"

    invalid = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "RESOLVED", "reasonCode": "OUT_OF_SCOPE"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_OUTCOME_REASON"

    resolved = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={
            "status": "RESOLVED",
            "reasonCode": "WORK_COMPLETED",
            "note": "Internal crew notes stay private.",
        },
    )
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()
    assert body["outcome"]["resolutionReasonCode"] == "WORK_COMPLETED"
    assert body["outcome"]["resolutionNote"] == "Internal crew notes stay private."
    assert body["outcome"]["resolutionCitizenMessage"] == citizen_safe_message("WORK_COMPLETED")
    assert body["outcome"]["resolvedBy"] == ADMIN_STAFF_ID


def test_direct_close_requires_rejection_reason(client: TestClient) -> None:
    created = _create_ticket(client)
    missing = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "CLOSED"},
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "OUTCOME_REASON_REQUIRED"

    closed = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "CLOSED", "reasonCode": "DUPLICATE", "note": "Matches BG-2026-0001."},
    )
    assert closed.status_code == 200
    assert closed.json()["outcome"]["closureReasonCode"] == "DUPLICATE"
    assert closed.json()["outcome"]["resolutionReasonCode"] is None


def test_closing_resolved_ticket_preserves_resolution(client: TestClient) -> None:
    created = _create_ticket(client)
    _advance_to_in_progress(client, created["ticketId"])
    client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "RESOLVED", "reasonCode": "TEMPORARY_FIX", "note": "Cold patch only."},
    )
    closed = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={
            "status": "CLOSED",
            "reasonCode": "CONFIRMED_COMPLETE",
            "note": "Supervisor signed off.",
        },
    )
    assert closed.status_code == 200
    outcome = closed.json()["outcome"]
    assert outcome["resolutionReasonCode"] == "TEMPORARY_FIX"
    assert outcome["resolutionNote"] == "Cold patch only."
    assert outcome["closureReasonCode"] == "CONFIRMED_COMPLETE"
    assert outcome["closureNote"] == "Supervisor signed off."


def test_legacy_terminal_tickets_remain_readable(client: TestClient) -> None:
    created = _create_ticket(client)
    ticket_store.patch_fields(created["ticketId"], {"status": "RESOLVED"})
    detail = client.get(f"/v1/tickets/{created['ticketId']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "RESOLVED"
    assert detail.json()["outcome"] is None

    tracking = client.get(f"/v1/tickets/track/{created['trackingCode']}")
    assert tracking.status_code == 200
    assert tracking.json()["status"] == "RESOLVED"
    assert tracking.json()["outcomeMessage"] is None


def test_citizen_tracking_exposes_safe_wording_not_private_notes(client: TestClient) -> None:
    created = _create_ticket(client)
    _advance_to_in_progress(client, created["ticketId"])
    client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={
            "status": "RESOLVED",
            "reasonCode": "WORK_COMPLETED",
            "note": "Used contractor invoice #4412.",
        },
    )

    tracking = client.get(f"/v1/tickets/track/{created['trackingCode']}")
    assert tracking.status_code == 200
    body = tracking.json()
    assert body["outcomeMessage"] == RESOLUTION_REASON_CODES["WORK_COMPLETED"]
    assert "4412" not in str(body)
    assert "WORK_COMPLETED" not in str(body)
    assert "resolutionNote" not in body
    assert "workOrder" not in str(body).lower() or "workOrderId" not in body


def test_activity_timeline_includes_work_order_events(client: TestClient) -> None:
    created = _create_ticket(client)
    _accept_ticket(client, created["ticketId"])
    work_order = client.post(f"/v1/tickets/{created['ticketId']}/work-orders", json={}).json()
    timeline = client.get(f"/v1/tickets/{created['ticketId']}/activity")
    assert timeline.status_code == 200
    types = {event["eventType"] for event in timeline.json()["events"]}
    assert "WORK_ORDER_CREATE" in types
    assert work_order["workOrderId"]
    assert any(
        entry.action_type == "WORK_ORDER_CREATE"
        for entry in audit_history_store.list_by_ticket_id(created["ticketId"])
    )


def test_outcome_kind_mapping() -> None:
    assert required_outcome_kind("IN_PROGRESS", "RESOLVED") == "resolution"
    assert required_outcome_kind("SUBMITTED", "CLOSED") == "rejection"
    assert required_outcome_kind("UNDER_REVIEW", "CLOSED") == "rejection"
    assert required_outcome_kind("RESOLVED", "CLOSED") == "closure"
    assert required_outcome_kind("UNDER_REVIEW", "ASSIGNED") is None
    assert "WORK_COMPLETED" in RESOLUTION_REASON_CODES
    assert "DUPLICATE" in REJECTION_REASON_CODES
    assert "CONFIRMED_COMPLETE" in CLOSURE_REASON_CODES
