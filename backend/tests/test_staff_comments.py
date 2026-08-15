from app.database.memory import ticket_store
from app.database.memory_audit_history import audit_history_store
from app.schemas.stored_audit_history import StoredAuditHistory
from tests.conftest import contribution_ready_auth_headers, issue_test_staff_token
from tests.test_submit_ticket import VALID_PAYLOAD


def _ticket(client):
    response = client.post(
        "/v1/tickets", json=VALID_PAYLOAD, headers=contribution_ready_auth_headers()
    )
    assert response.status_code == 201
    return response.json()["ticketId"]


def _headers(client, username="admin"):
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username=username)}"}


def test_staff_comments_are_private_append_only_and_present_in_activity(anonymous_client):
    ticket_id = _ticket(anonymous_client)
    created = anonymous_client.post(
        f"/v1/tickets/{ticket_id}/comments",
        json={
            "text": "Please review this with the roads team.",
            "mentionedStaffIds": ["staff_muni_001"],
        },
        headers=_headers(anonymous_client),
    )
    assert created.status_code == 201, created.text
    assert created.json()["authorStaffId"] == "staff_admin_001"
    assert created.json()["mentionedStaffIds"] == ["staff_muni_001"]
    activity = anonymous_client.get(
        f"/v1/tickets/{ticket_id}/activity", headers=_headers(anonymous_client)
    )
    assert activity.status_code == 200
    assert any(event["eventType"] == "STAFF_COMMENT" for event in activity.json()["events"])
    assert "Please review" not in str(activity.json())
    assert anonymous_client.get(f"/v1/tickets/{ticket_id}/comments").status_code == 401


def test_comments_reject_invalid_mentions_and_out_of_scope_ticket(anonymous_client):
    ticket_id = _ticket(anonymous_client)
    invalid = anonymous_client.post(
        f"/v1/tickets/{ticket_id}/comments",
        json={"text": "x", "mentionedStaffIds": ["missing"]},
        headers=_headers(anonymous_client),
    )
    assert invalid.status_code == 400
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    ticket_store.save(
        stored.model_copy(update={"department_id": "d2222222-2222-2222-2222-222222222222"})
    )
    out_of_scope = anonymous_client.get(
        f"/v1/tickets/{ticket_id}/activity", headers=_headers(anonymous_client, "staff")
    )
    assert out_of_scope.status_code == 404


def test_activity_projects_operational_audits_safely_and_paginates_by_event_key(anonymous_client):
    ticket_id = _ticket(anonymous_client)
    for index in range(3):
        audit_history_store.append(
            StoredAuditHistory(
                auditId=f"audit-271-{index}",
                ticketId=ticket_id,
                actionType="WORK_ORDER_ASSIGN",
                actorId="staff_admin_001",
                actorRole="administrator",
                summary=f"Assignment {index}",
                previousValue="worker-old" if index else None,
                newValue="worker-new",
                createdAt=f"2099-01-01T00:00:0{index}Z",
            )
        )

    headers = _headers(anonymous_client)
    first = anonymous_client.get(
        f"/v1/tickets/{ticket_id}/activity?limit=2", headers=headers
    )
    assert first.status_code == 200, first.text
    assert len(first.json()["events"]) == 2
    projected = next(
        event for event in first.json()["events"] if event["eventType"] == "WORK_ORDER_ASSIGN"
    )
    assert projected["actorDisplayName"] == "Demo Administrator"
    assert "worker-new" not in first.text
    assert "staff_admin_001" not in first.text

    second = anonymous_client.get(
        f"/v1/tickets/{ticket_id}/activity?limit=2&cursor={first.json()['nextCursor']}",
        headers=headers,
    )
    assert second.status_code == 200, second.text
    assert [event["eventId"] for event in second.json()["events"]] == [
        "audit:audit-271-1",
        "audit:audit-271-2",
    ]

    audit_history_store.append(
        StoredAuditHistory(
            auditId="audit-271-new",
            ticketId=ticket_id,
            actionType="WORK_ORDER_COMPLETE",
            actorId="missing-staff",
            actorRole="administrator",
            summary="Completed",
            createdAt="2099-01-01T00:00:04Z",
        )
    )
    stable = anonymous_client.get(
        f"/v1/tickets/{ticket_id}/activity?limit=2&cursor={first.json()['nextCursor']}",
        headers=headers,
    )
    assert [event["eventId"] for event in stable.json()["events"]] == [
        "audit:audit-271-1",
        "audit:audit-271-2",
    ]
