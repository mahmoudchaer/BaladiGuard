"""End-to-end municipal staff operations joins (issue #318)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.database.memory import ticket_store
from app.main import app
from tests.conftest import issue_test_staff_token
from tests.test_workforce import (
    BEIRUT,
    ROAD,
    _create_team,
    _create_ticket,
    _create_worker,
    _stamp_ticket,
)


def _admin(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username='admin')}"}


def _staff(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username='staff')}"}


def test_team_lead_must_be_a_member(client: TestClient) -> None:
    admin = _admin(client)
    member = _create_worker(client, name="Lead candidate")
    outsider = _create_worker(client, name="Outsider")
    created = client.post(
        "/v1/workforce/teams",
        json={
            "municipalityId": BEIRUT,
            "displayName": "Lead team",
            "departmentIds": [ROAD],
            "workerIds": [member["workerId"]],
            "leadWorkerId": outsider["workerId"],
        },
        headers=admin,
    )
    assert created.status_code == 400, created.text

    team = _create_team(client, worker_ids=[member["workerId"]])
    updated = client.patch(
        f"/v1/workforce/teams/{team['teamId']}",
        json={"leadWorkerId": member["workerId"]},
        headers=admin,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["leadWorkerId"] == member["workerId"]


def test_aggregates_match_workload_buckets(client: TestClient) -> None:
    queued = _create_ticket(client)
    _stamp_ticket(queued, status="SUBMITTED")
    assigned = _create_ticket(client)
    _stamp_ticket(assigned, status="ASSIGNED")
    worker = _create_worker(client)
    staff = _staff(client)
    client.post(
        f"/v1/tickets/{assigned}/workforce-assignment",
        json={"workerId": worker["workerId"]},
        headers=staff,
    )

    workload = client.get("/v1/workforce/workload", headers=staff)
    aggregates = client.get("/v1/tickets/aggregates", headers=staff)
    assert workload.status_code == 200
    assert aggregates.status_code == 200
    body = aggregates.json()
    assert body["approximate"] is False
    assert body["workforceUnassignedCount"] == len(workload.json()["unassignedTickets"])
    assert body["assignedCount"] >= 1
    assert body["queuedCount"] >= 1
    assert "completedCount" in body
    assert "cancelledCount" in body


def test_assignment_history_and_scope(client: TestClient) -> None:
    ticket_id = _create_ticket(client)
    _stamp_ticket(ticket_id)
    worker = _create_worker(client)
    staff = _staff(client)
    assigned = client.post(
        f"/v1/tickets/{ticket_id}/workforce-assignment",
        json={"workerId": worker["workerId"]},
        headers=staff,
    )
    assert assigned.status_code == 200, assigned.text

    history = client.get(f"/v1/tickets/{ticket_id}/assignment-history", headers=staff)
    assert history.status_code == 200, history.text
    actions = {item["actionType"] for item in history.json()["items"]}
    assert "WORKFORCE_ASSIGN" in actions

    assert TestClient(app).get(f"/v1/tickets/{ticket_id}/assignment-history").status_code == 401


def test_bulk_workforce_preview_then_assign(client: TestClient) -> None:
    first = _create_ticket(client)
    second = _create_ticket(client)
    _stamp_ticket(first)
    _stamp_ticket(second)
    worker = _create_worker(client)
    staff = _staff(client)
    preview = client.post(
        "/v1/tickets/bulk/workforce-assignment",
        json={"ticketIds": [first, second], "workerId": worker["workerId"], "dryRun": True},
        headers=staff,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["dryRun"] is True
    assert preview.json()["succeeded"] == 2
    stored = ticket_store.get(first)
    assert stored is not None
    assert stored.assigned_worker_id is None

    committed = client.post(
        "/v1/tickets/bulk/workforce-assignment",
        json={"ticketIds": [first, second], "workerId": worker["workerId"]},
        headers=staff,
    )
    assert committed.status_code == 200, committed.text
    assert committed.json()["failed"] == 0
    assert ticket_store.get(first).assigned_worker_id == worker["workerId"]


def test_bulk_preview_validates_missing_worker(client: TestClient) -> None:
    ticket_id = _create_ticket(client)
    _stamp_ticket(ticket_id)
    staff = _staff(client)
    preview = client.post(
        "/v1/tickets/bulk/workforce-assignment",
        json={"ticketIds": [ticket_id], "workerId": "worker_does_not_exist", "dryRun": True},
        headers=staff,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["dryRun"] is True
    assert body["failed"] == 1
    assert body["items"][0]["ok"] is False
    assert body["items"][0]["code"] == "WORKER_NOT_FOUND"
    assert ticket_store.get(ticket_id).assigned_worker_id is None


def test_closed_tickets_count_in_exactly_one_terminal_bucket(client: TestClient) -> None:
    staff = _staff(client)
    before = client.get("/v1/tickets/aggregates", headers=staff).json()

    completed_id = _create_ticket(client)
    cancelled_id = _create_ticket(client)
    completed = ticket_store.get(completed_id)
    cancelled = ticket_store.get(cancelled_id)
    assert completed is not None and cancelled is not None
    ticket_store.save(
        completed.model_copy(update={"status": "CLOSED", "resolved_at": "2026-08-01T00:00:00Z"})
    )
    ticket_store.save(cancelled.model_copy(update={"status": "CLOSED", "resolved_at": None}))

    after = client.get("/v1/tickets/aggregates", headers=staff).json()
    assert after["completedCount"] == before["completedCount"] + 1
    assert after["cancelledCount"] == before["cancelledCount"] + 1


def test_close_blocked_while_active_work_order(client: TestClient) -> None:
    ticket_id = _create_ticket(client)
    _stamp_ticket(ticket_id, status="UNDER_REVIEW")
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    ticket_store.save(stored.model_copy(update={"active_work_order_id": "wo_test_block_close"}))
    staff = _staff(client)
    closed = client.patch(
        f"/v1/tickets/{ticket_id}/status",
        json={"status": "CLOSED", "reasonCode": "DUPLICATE"},
        headers=staff,
    )
    assert closed.status_code == 400, closed.text
    assert closed.json()["error"]["code"] == "ACTIVE_WORK_ORDER"


def test_cross_municipality_assignment_history_is_hidden(client: TestClient) -> None:
    ticket_id = _create_ticket(client)
    _stamp_ticket(ticket_id, municipality_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    staff = _staff(client)
    response = client.get(f"/v1/tickets/{ticket_id}/assignment-history", headers=staff)
    assert response.status_code == 404
