"""Citizen resolution verification and staff review (issues #248 / #261)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.database.memory import ticket_store
from app.database.memory_audit_history import audit_history_store
from app.database.memory_notification_delivery import notification_delivery_store
from app.main import app
from app.services.ai_job_queue import ai_job_queue
from tests.conftest import contribution_ready_auth_headers, issue_test_staff_token
from tests.test_submit_ticket import VALID_PAYLOAD
from tests.test_workforce import BEIRUT, ROAD


def _admin(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username='admin')}"}


def _staff(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username='staff')}"}


def _create_ticket(client: TestClient, headers: dict[str, str] | None = None) -> dict:
    response = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=headers or contribution_ready_auth_headers(),
    )
    assert response.status_code == 201, response.text
    assert ai_job_queue.run_once().outcome == "succeeded"
    return response.json()


def _resolve_ticket(client: TestClient, ticket_id: str) -> None:
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    ticket_store.save(
        stored.model_copy(
            update={
                "municipality_id": BEIRUT,
                "department_id": ROAD,
                "status": "IN_PROGRESS",
            }
        )
    )
    resolved = client.patch(
        f"/v1/tickets/{ticket_id}/status",
        json={"status": "RESOLVED", "reasonCode": "WORK_COMPLETED"},
        headers=_admin(client),
    )
    assert resolved.status_code == 200, resolved.text


def test_owner_can_submit_and_retry_resolution_feedback(client: TestClient) -> None:
    owner = contribution_ready_auth_headers()
    created = _create_ticket(client, owner)
    _resolve_ticket(client, created["ticketId"])

    history = client.get("/v1/citizen/me/tickets", headers=owner)
    assert history.status_code == 200
    item = next(
        row for row in history.json()["items"] if row["trackingCode"] == created["trackingCode"]
    )
    assert item["canSubmitResolutionFeedback"] is True
    assert item["resolutionFeedbackStatus"] is None

    path = f"/v1/citizen/me/tickets/{created['trackingCode']}/resolution-feedback"
    first = client.post(
        path,
        json={"status": "CONFIRMED_FIXED", "note": "Looks good."},
        headers=owner,
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "CONFIRMED_FIXED"
    assert first.json()["canSubmit"] is False
    assert "note" not in first.json()

    retry = client.post(
        path, json={"status": "CONFIRMED_FIXED", "note": "Looks good."}, headers=owner
    )
    assert retry.status_code == 200
    assert retry.json()["submittedAt"] == first.json()["submittedAt"]

    changed = client.post(path, json={"status": "STILL_UNRESOLVED"}, headers=owner)
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "RESOLUTION_FEEDBACK_ALREADY_SUBMITTED"

    refreshed = client.get("/v1/citizen/me/tickets", headers=owner).json()["items"][0]
    assert refreshed["canSubmitResolutionFeedback"] is False
    assert refreshed["resolutionFeedbackStatus"] == "CONFIRMED_FIXED"


def test_feedback_requires_owner_resolved_account_linked_ticket(client: TestClient) -> None:
    owner = contribution_ready_auth_headers()
    other = contribution_ready_auth_headers(phone="+96171111111", full_name="Other Citizen")
    created = _create_ticket(client, owner)
    path = f"/v1/citizen/me/tickets/{created['trackingCode']}/resolution-feedback"

    not_resolved = client.post(path, json={"status": "CONFIRMED_FIXED"}, headers=owner)
    assert not_resolved.status_code == 400
    assert not_resolved.json()["error"]["code"] == "FEEDBACK_NOT_ELIGIBLE"

    _resolve_ticket(client, created["ticketId"])

    anonymous = client.post(path, json={"status": "CONFIRMED_FIXED"})
    assert anonymous.status_code == 401

    stranger = client.post(path, json={"status": "CONFIRMED_FIXED"}, headers=other)
    assert stranger.status_code == 404

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    ticket_store.save(stored.model_copy(update={"owner_user_id": None}))
    unowned = client.post(path, json={"status": "CONFIRMED_FIXED"}, headers=owner)
    assert unowned.status_code == 404


def test_still_unresolved_alerts_review_queue_and_does_not_reopen(client: TestClient) -> None:
    owner = contribution_ready_auth_headers()
    created = _create_ticket(client, owner)
    _resolve_ticket(client, created["ticketId"])
    path = f"/v1/citizen/me/tickets/{created['trackingCode']}/resolution-feedback"
    submitted = client.post(
        path,
        json={"status": "STILL_UNRESOLVED", "note": "The hole is still there."},
        headers=owner,
    )
    assert submitted.status_code == 200
    assert client.get(f"/v1/tickets/{created['ticketId']}").json()["status"] == "RESOLVED"

    queue = client.get("/v1/resolution-reviews", headers=_admin(client))
    assert queue.status_code == 200
    assert any(item["ticketId"] == created["ticketId"] for item in queue.json()["items"])

    staff_view = client.get(
        f"/v1/tickets/{created['ticketId']}/resolution-feedback", headers=_admin(client)
    )
    assert staff_view.status_code == 200
    assert staff_view.json()["note"] == "The hole is still there."
    assert staff_view.json()["needsReview"] is True

    blocked = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "CLOSED", "reasonCode": "CONFIRMED_COMPLETE"},
        headers=_admin(client),
    )
    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "RESOLUTION_FEEDBACK_REVIEW_REQUIRED"


def test_staff_review_can_keep_resolved_or_return_in_progress(client: TestClient) -> None:
    owner = contribution_ready_auth_headers()
    created = _create_ticket(client, owner)
    _resolve_ticket(client, created["ticketId"])
    client.post(
        f"/v1/citizen/me/tickets/{created['trackingCode']}/resolution-feedback",
        json={"status": "STILL_UNRESOLVED", "note": "Still broken."},
        headers=owner,
    )

    keep = client.post(
        f"/v1/tickets/{created['ticketId']}/resolution-feedback/review",
        json={"action": "KEEP_RESOLVED"},
        headers=_admin(client),
    )
    assert keep.status_code == 200, keep.text
    assert keep.json()["reviewAction"] == "KEEP_RESOLVED"
    assert keep.json()["needsReview"] is False
    assert client.get(f"/v1/tickets/{created['ticketId']}").json()["status"] == "RESOLVED"
    closed = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "CLOSED", "reasonCode": "CONFIRMED_COMPLETE"},
        headers=_admin(client),
    )
    assert closed.status_code == 200


def test_staff_can_explicitly_return_ticket_to_in_progress(client: TestClient) -> None:
    owner = contribution_ready_auth_headers()
    created = _create_ticket(client, owner)
    _resolve_ticket(client, created["ticketId"])
    client.post(
        f"/v1/citizen/me/tickets/{created['trackingCode']}/resolution-feedback",
        json={"status": "STILL_UNRESOLVED"},
        headers=owner,
    )

    returned = client.post(
        f"/v1/tickets/{created['ticketId']}/resolution-feedback/review",
        json={"action": "RETURN_IN_PROGRESS"},
        headers=_admin(client),
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["reviewAction"] == "RETURN_IN_PROGRESS"
    assert client.get(f"/v1/tickets/{created['ticketId']}").json()["status"] == "IN_PROGRESS"
    assert client.get("/v1/resolution-reviews", headers=_admin(client)).json()["items"] == []

    retry_same = client.post(
        f"/v1/tickets/{created['ticketId']}/resolution-feedback/review",
        json={"action": "RETURN_IN_PROGRESS"},
        headers=_admin(client),
    )
    assert retry_same.status_code == 200


def test_public_and_other_citizen_never_see_note_or_identity(client: TestClient) -> None:
    owner = contribution_ready_auth_headers()
    created = _create_ticket(client, owner)
    _resolve_ticket(client, created["ticketId"])
    client.post(
        f"/v1/citizen/me/tickets/{created['trackingCode']}/resolution-feedback",
        json={"status": "STILL_UNRESOLVED", "note": "secret-private-note"},
        headers=owner,
    )

    tracking = client.get(f"/v1/tickets/track/{created['trackingCode']}")
    assert tracking.status_code == 200
    body = tracking.text
    assert "secret-private-note" not in body
    assert "resolutionFeedback" not in body
    assert "ownerUserId" not in body

    history = client.get("/v1/citizen/me/tickets", headers=owner).json()
    assert "secret-private-note" not in str(history)

    owner_view = client.get(
        f"/v1/citizen/me/tickets/{created['trackingCode']}/resolution-feedback",
        headers=owner,
    )
    assert owner_view.status_code == 200
    assert "note" not in owner_view.json()
    assert "secret-private-note" not in owner_view.text


def test_feedback_audit_and_receipt_omit_private_content(client: TestClient) -> None:
    owner = contribution_ready_auth_headers()
    created = _create_ticket(client, owner)
    _resolve_ticket(client, created["ticketId"])
    client.post(
        f"/v1/citizen/me/tickets/{created['trackingCode']}/resolution-feedback",
        json={"status": "STILL_UNRESOLVED", "note": "do-not-log-this-note"},
        headers=owner,
    )

    entries = [
        entry
        for entry in audit_history_store.list_by_ticket_id(created["ticketId"])
        if entry.action_type == "RESOLUTION_FEEDBACK_SUBMIT"
    ]
    assert entries
    serialized = str(entries[0].model_dump())
    assert "do-not-log-this-note" not in serialized
    assert entries[0].actor_id is None
    assert entries[0].new_value == "STILL_UNRESOLVED"

    deliveries = [
        item
        for item in notification_delivery_store.list_all()
        if item.event == "resolution_feedback_received"
    ]
    assert deliveries
    assert "do-not-log-this-note" not in str(deliveries[0].model_dump())


def test_staff_feedback_endpoints_are_permission_scoped(client: TestClient) -> None:
    owner = contribution_ready_auth_headers()
    created = _create_ticket(client, owner)
    _resolve_ticket(client, created["ticketId"])
    client.post(
        f"/v1/citizen/me/tickets/{created['trackingCode']}/resolution-feedback",
        json={"status": "STILL_UNRESOLVED"},
        headers=owner,
    )

    anonymous = TestClient(app).get(f"/v1/tickets/{created['ticketId']}/resolution-feedback")
    assert anonymous.status_code == 401

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    ticket_store.save(
        stored.model_copy(update={"municipality_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"})
    )
    other_staff = client.get(
        f"/v1/tickets/{created['ticketId']}/resolution-feedback", headers=_staff(client)
    )
    assert other_staff.status_code == 404
