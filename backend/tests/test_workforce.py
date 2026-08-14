"""Municipality workforce directory, assignment, and workload (issue #245)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.database.dynamo_workforce_store import DynamoWorkforceStore
from app.database.dynamodb_tables import TABLE_DEFINITIONS
from app.database.memory import ticket_store
from app.schemas.workforce import StoredTeam, StoredWorker
from app.services.ai_job_queue import ai_job_queue
from tests.conftest import contribution_ready_auth_headers, issue_test_staff_token
from tests.test_submit_ticket import VALID_PAYLOAD

BEIRUT = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
OTHER_MUNICIPALITY = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ROAD = "d1111111-1111-1111-1111-111111111111"
WASTE = "d2222222-2222-2222-2222-222222222222"


def _admin(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username='admin')}"}


def _staff(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username='staff')}"}


def _create_ticket(client: TestClient) -> str:
    response = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=contribution_ready_auth_headers(),
    )
    assert response.status_code == 201, response.text
    assert ai_job_queue.run_once().outcome == "succeeded"
    return response.json()["ticketId"]


def _stamp_ticket(
    ticket_id: str,
    *,
    municipality_id: str | None = BEIRUT,
    department_id: str | None = ROAD,
    status: str | None = None,
) -> None:
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    updates: dict[str, object] = {
        "municipality_id": municipality_id,
        "department_id": department_id,
    }
    if status is not None:
        updates["status"] = status
    ticket_store.save(stored.model_copy(update=updates))


def _create_worker(
    client: TestClient,
    *,
    name: str = "Road crew A",
    departments: list[str] | None = None,
    municipality_id: str = BEIRUT,
    headers: dict[str, str] | None = None,
) -> dict:
    response = client.post(
        "/v1/workforce/workers",
        json={
            "municipalityId": municipality_id,
            "displayName": name,
            "departmentIds": departments or [ROAD],
        },
        headers=headers or _admin(client),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_team(
    client: TestClient,
    *,
    name: str = "Night roads",
    departments: list[str] | None = None,
    worker_ids: list[str] | None = None,
    headers: dict[str, str] | None = None,
) -> dict:
    response = client.post(
        "/v1/workforce/teams",
        json={
            "municipalityId": BEIRUT,
            "displayName": name,
            "departmentIds": departments or [ROAD],
            "workerIds": worker_ids or [],
        },
        headers=headers or _admin(client),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_workforce_tables_are_defined() -> None:
    suffixes = {item["suffix"] for item in TABLE_DEFINITIONS}
    assert "workforce-workers" in suffixes
    assert "workforce-teams" in suffixes


def test_anonymous_workforce_routes_are_unauthorized(anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/v1/workforce/workers").status_code == 401
    assert anonymous_client.get("/v1/workforce/workload").status_code == 401
    assert anonymous_client.post("/v1/workforce/workers", json={}).status_code == 401


def test_municipal_staff_cannot_mutate_directory(client: TestClient) -> None:
    staff = _staff(client)
    created = client.post(
        "/v1/workforce/workers",
        json={"displayName": "Crew", "departmentIds": [ROAD], "municipalityId": BEIRUT},
        headers=staff,
    )
    assert created.status_code == 403
    listed = client.get("/v1/workforce/workers", headers=staff)
    assert listed.status_code == 200


def test_admin_worker_and_team_crud_and_membership(client: TestClient) -> None:
    admin = _admin(client)
    worker = _create_worker(client, name="Karim Roads")
    assert worker["workerId"].startswith("wrk_")
    assert worker["active"] is True
    assert "contact" not in worker
    team = _create_team(client, name="Pothole unit", worker_ids=[worker["workerId"]])
    assert team["teamId"].startswith("team_")
    assert worker["workerId"] in team["workerIds"]

    refreshed = client.get("/v1/workforce/workers", headers=admin)
    assert refreshed.status_code == 200
    match = next(item for item in refreshed.json() if item["workerId"] == worker["workerId"])
    assert team["teamId"] in match["teamIds"]

    renamed = client.patch(
        f"/v1/workforce/workers/{worker['workerId']}",
        json={"displayName": "Karim Roads (lead)"},
        headers=admin,
    )
    assert renamed.status_code == 200
    assert renamed.json()["displayName"] == "Karim Roads (lead)"


def test_staff_assigns_worker_xor_team_and_writes_audit(client: TestClient) -> None:
    ticket_id = _create_ticket(client)
    _stamp_ticket(ticket_id)
    worker = _create_worker(client)
    team = _create_team(client)
    staff = _staff(client)

    both = client.post(
        f"/v1/tickets/{ticket_id}/workforce-assignment",
        json={"workerId": worker["workerId"], "teamId": team["teamId"]},
        headers=staff,
    )
    assert both.status_code == 400

    assigned = client.post(
        f"/v1/tickets/{ticket_id}/workforce-assignment",
        json={"workerId": worker["workerId"]},
        headers=staff,
    )
    assert assigned.status_code == 200, assigned.text
    body = assigned.json()
    assert body["assignedWorkerId"] == worker["workerId"]
    assert body["assignedTeamId"] is None
    audit_types = [entry["actionType"] for entry in body["auditHistory"]]
    assert "WORKFORCE_ASSIGN" in audit_types
    assert any(entry.get("actorId") for entry in body["auditHistory"])

    listed = client.get(f"/v1/tickets?workerId={worker['workerId']}", headers=staff)
    assert listed.status_code == 200
    assert any(item["ticketId"] == ticket_id for item in listed.json()["items"])

    to_team = client.post(
        f"/v1/tickets/{ticket_id}/workforce-assignment",
        json={"teamId": team["teamId"]},
        headers=staff,
    )
    assert to_team.status_code == 200
    assert to_team.json()["assignedTeamId"] == team["teamId"]
    assert to_team.json()["assignedWorkerId"] is None


def test_assignment_rejects_unknown_inactive_and_out_of_scope(client: TestClient) -> None:
    ticket_id = _create_ticket(client)
    _stamp_ticket(ticket_id, municipality_id=BEIRUT, department_id=ROAD)
    staff = _staff(client)
    waste_worker = _create_worker(client, name="Waste only", departments=[WASTE])
    other = _create_worker(client, name="Other city")
    client.patch(
        f"/v1/workforce/workers/{other['workerId']}",
        json={"municipalityId": OTHER_MUNICIPALITY},
        headers=_admin(client),
    )
    # Municipality cannot be changed; stamp a foreign worker directly.
    from app.database.memory_workforce import workforce_store

    stored = workforce_store.get_worker(other["workerId"])
    assert stored is not None
    workforce_store.save_worker(stored.model_copy(update={"municipality_id": OTHER_MUNICIPALITY}))

    unknown = client.post(
        f"/v1/tickets/{ticket_id}/workforce-assignment",
        json={"workerId": "wrk_missing"},
        headers=staff,
    )
    assert unknown.status_code == 404

    wrong_dept = client.post(
        f"/v1/tickets/{ticket_id}/workforce-assignment",
        json={"workerId": waste_worker["workerId"]},
        headers=staff,
    )
    assert wrong_dept.status_code == 400

    cross = client.post(
        f"/v1/tickets/{ticket_id}/workforce-assignment",
        json={"workerId": other["workerId"]},
        headers=staff,
    )
    assert cross.status_code in {400, 403}

    inactive = _create_worker(client, name="Inactive roads")
    deact = client.post(
        f"/v1/workforce/workers/{inactive['workerId']}/deactivate",
        headers=_admin(client),
    )
    assert deact.status_code == 200
    assert deact.json()["active"] is False
    blocked = client.post(
        f"/v1/tickets/{ticket_id}/workforce-assignment",
        json={"workerId": inactive["workerId"]},
        headers=staff,
    )
    assert blocked.status_code == 400


def test_deactivation_keeps_historical_assignment(client: TestClient) -> None:
    ticket_id = _create_ticket(client)
    _stamp_ticket(ticket_id, status="ASSIGNED")
    worker = _create_worker(client)
    staff = _staff(client)
    assigned = client.post(
        f"/v1/tickets/{ticket_id}/workforce-assignment",
        json={"workerId": worker["workerId"]},
        headers=staff,
    )
    assert assigned.status_code == 200
    client.post(
        f"/v1/workforce/workers/{worker['workerId']}/deactivate",
        headers=_admin(client),
    )
    detail = client.get(f"/v1/tickets/{ticket_id}", headers=staff)
    assert detail.json()["assignedWorkerId"] == worker["workerId"]
    client.post(
        f"/v1/workforce/workers/{worker['workerId']}/reactivate",
        headers=_admin(client),
    )


def test_workload_excludes_resolved_and_has_unassigned_bucket(client: TestClient) -> None:
    open_id = _create_ticket(client)
    _stamp_ticket(open_id, status="IN_PROGRESS")
    resolved_id = _create_ticket(client)
    _stamp_ticket(resolved_id, status="RESOLVED")
    assigned_id = _create_ticket(client)
    _stamp_ticket(assigned_id, status="ASSIGNED")
    worker = _create_worker(client)
    staff = _staff(client)
    client.post(
        f"/v1/tickets/{assigned_id}/workforce-assignment",
        json={"workerId": worker["workerId"]},
        headers=staff,
    )

    workload = client.get("/v1/workforce/workload", headers=staff)
    assert workload.status_code == 200, workload.text
    body = workload.json()
    assert "contact" not in body
    unassigned_ids = {item["ticketId"] for item in body["unassignedTickets"]}
    assert open_id in unassigned_ids
    assert resolved_id not in unassigned_ids
    worker_row = next(item for item in body["workers"] if item["id"] == worker["workerId"])
    assert worker_row["counts"]["assigned"] == 1
    assert worker_row["counts"]["inProgress"] == 0
    assert resolved_id not in {item["ticketId"] for item in worker_row["tickets"]}
    assert assigned_id in {item["ticketId"] for item in worker_row["tickets"]}

    drill = client.get("/v1/tickets?workforceUnassigned=true&openOnly=true", headers=staff)
    assert drill.status_code == 200
    drill_ids = {item["ticketId"] for item in drill.json()["items"]}
    assert open_id in drill_ids
    assert assigned_id not in drill_ids


def test_dynamo_workforce_store_round_trip(dynamodb_settings: Settings) -> None:
    store = DynamoWorkforceStore(dynamodb_settings)
    worker = StoredWorker(
        workerId="wrk_test1",
        municipalityId=BEIRUT,
        displayName="Dynamo worker",
        departmentIds=[ROAD],
        teamIds=[],
        active=True,
        createdAt="2026-08-14T12:00:00Z",
        updatedAt="2026-08-14T12:00:00Z",
    )
    store.save_worker(worker)
    loaded = store.get_worker("wrk_test1")
    assert loaded is not None
    assert loaded.display_name == "Dynamo worker"
    listed = store.list_workers(BEIRUT)
    assert any(item.worker_id == "wrk_test1" for item in listed)

    team = StoredTeam(
        teamId="team_test1",
        municipalityId=BEIRUT,
        displayName="Dynamo team",
        departmentIds=[ROAD],
        workerIds=["wrk_test1"],
        active=True,
        createdAt="2026-08-14T12:00:00Z",
        updatedAt="2026-08-14T12:00:00Z",
    )
    store.save_team(team)
    assert store.get_team("team_test1") is not None
    assert store.claim_worker("wrk_test1", worker.updated_at, ROAD) is True
    assert store.claim_worker("wrk_test1", worker.updated_at, ROAD) is False
    refreshed = store.get_worker("wrk_test1")
    assert refreshed is not None
    assert store.claim_worker(refreshed.worker_id, refreshed.updated_at, WASTE) is False


def test_assignment_rejects_stale_read_after_deactivation(client: TestClient) -> None:
    ticket_id = _create_ticket(client)
    _stamp_ticket(ticket_id)
    worker = _create_worker(client)
    from app.database.memory_workforce import workforce_store

    stale = workforce_store.get_worker(worker["workerId"])
    assert stale is not None
    deact = client.post(
        f"/v1/workforce/workers/{worker['workerId']}/deactivate",
        headers=_admin(client),
    )
    assert deact.status_code == 200
    original = workforce_store.get_worker
    calls = {"n": 0}

    def stale_first(worker_id: str):
        calls["n"] += 1
        if worker_id == worker["workerId"] and calls["n"] == 1:
            return stale
        return original(worker_id)

    workforce_store.get_worker = stale_first  # type: ignore[method-assign]
    try:
        blocked = client.post(
            f"/v1/tickets/{ticket_id}/workforce-assignment",
            json={"workerId": worker["workerId"]},
            headers=_staff(client),
        )
        assert blocked.status_code == 400
    finally:
        workforce_store.get_worker = original  # type: ignore[method-assign]


def test_assignment_rejects_stale_read_after_department_change(client: TestClient) -> None:
    ticket_id = _create_ticket(client)
    _stamp_ticket(ticket_id, department_id=ROAD)
    worker = _create_worker(client, departments=[ROAD])
    from app.database.memory_workforce import workforce_store

    stale = workforce_store.get_worker(worker["workerId"])
    assert stale is not None
    moved = client.patch(
        f"/v1/workforce/workers/{worker['workerId']}",
        json={"departmentIds": [WASTE]},
        headers=_admin(client),
    )
    assert moved.status_code == 200
    original = workforce_store.get_worker
    calls = {"n": 0}

    def stale_first(worker_id: str):
        calls["n"] += 1
        if worker_id == worker["workerId"] and calls["n"] == 1:
            return stale
        return original(worker_id)

    workforce_store.get_worker = stale_first  # type: ignore[method-assign]
    try:
        blocked = client.post(
            f"/v1/tickets/{ticket_id}/workforce-assignment",
            json={"workerId": worker["workerId"]},
            headers=_staff(client),
        )
        assert blocked.status_code == 400
    finally:
        workforce_store.get_worker = original  # type: ignore[method-assign]


def test_assignment_conflict_when_claim_never_succeeds(client: TestClient) -> None:
    ticket_id = _create_ticket(client)
    _stamp_ticket(ticket_id)
    worker = _create_worker(client)
    from app.database.memory_workforce import workforce_store

    original = workforce_store.claim_worker
    workforce_store.claim_worker = lambda *_args, **_kwargs: False  # type: ignore[method-assign]
    try:
        conflict = client.post(
            f"/v1/tickets/{ticket_id}/workforce-assignment",
            json={"workerId": worker["workerId"]},
            headers=_staff(client),
        )
        assert conflict.status_code == 409
    finally:
        workforce_store.claim_worker = original  # type: ignore[method-assign]


def test_workload_follows_staff_page_cursors(client: TestClient, monkeypatch) -> None:
    from types import SimpleNamespace

    from app.services.complaints.ticket_service import ticket_service

    ticket_id = _create_ticket(client)
    _stamp_ticket(ticket_id, status="SUBMITTED")
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    page_one = [
        stored.model_copy(
            update={"ticket_id": f"tkt_page1_{index}", "ticket_number": f"BG-P1-{index:04d}"}
        )
        for index in range(100)
    ]
    extra = stored.model_copy(
        update={"ticket_id": "tkt_beyond_sample", "ticket_number": "BG-BEYOND"}
    )
    pages = [
        SimpleNamespace(items=page_one, next_cursor="page-2"),
        SimpleNamespace(items=[extra], next_cursor=None),
    ]
    state = {"index": 0}

    def fake_page(**_kwargs):
        page = pages[state["index"]]
        state["index"] += 1
        return page

    monkeypatch.setattr(ticket_service._store, "list_staff_page", fake_page)
    workload = client.get("/v1/workforce/workload", headers=_staff(client))
    assert workload.status_code == 200, workload.text
    unassigned_ids = {item["ticketId"] for item in workload.json()["unassignedTickets"]}
    assert "tkt_page1_0" in unassigned_ids
    assert "tkt_beyond_sample" in unassigned_ids
