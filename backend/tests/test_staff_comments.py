from app.core.staff_auth import principal_from_user
from app.database.memory import ticket_store
from app.database.memory_audit_history import audit_history_store
from app.database.store_factory import get_staff_store
from app.schemas.staff_comment import ActivityEvent, StoredStaffComment
from app.schemas.stored_audit_history import StoredAuditHistory
from app.schemas.stored_status_history import StoredStatusHistory
from app.services.staff import comments as comments_module
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
                summary=("Work order wo_123 assigned to worker wrk_456 for team team_789"),
                previousValue="worker-old" if index else None,
                newValue="worker-new",
                createdAt=f"2099-01-01T00:00:0{index}Z",
            )
        )

    headers = _headers(anonymous_client)
    first = anonymous_client.get(f"/v1/tickets/{ticket_id}/activity?limit=2", headers=headers)
    assert first.status_code == 200, first.text
    assert len(first.json()["events"]) == 2
    projected = next(
        event for event in first.json()["events"] if event["eventType"] == "WORK_ORDER_ASSIGN"
    )
    assert projected["actorDisplayName"] == "Demo Administrator"
    assert projected["details"]["summary"] == "Work order assignment changed."
    assert "wo_123" not in first.text
    assert "wrk_456" not in first.text
    assert "team_789" not in first.text
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


def test_activity_storage_cursor_merges_interleaved_source_pages_exactly_once(
    anonymous_client, monkeypatch
):
    ticket_id = _ticket(anonymous_client)
    principal = principal_from_user(get_staff_store().get("staff_admin_001"))

    class PagedStore:
        def __init__(self, pages):
            self.pages = pages
            self.calls = []

        def list_by_ticket_id_page(self, ticket_id, *, limit, exclusive_start_key=None):
            index = 0 if exclusive_start_key is None else exclusive_start_key["page"]
            self.calls.append((limit, index))
            page = self.pages[index]
            next_key = {"page": index + 1} if index + 1 < len(self.pages) else None
            return page, next_key

    status = PagedStore(
        [
            [
                StoredStatusHistory(
                    historyId="h1",
                    ticketId=ticket_id,
                    newStatus="SUBMITTED",
                    updatedBy="staff_admin_001",
                    createdAt="2026-01-01T00:00:01Z",
                )
            ],
            [
                StoredStatusHistory(
                    historyId="h2",
                    ticketId=ticket_id,
                    newStatus="UNDER_REVIEW",
                    updatedBy="staff_admin_001",
                    createdAt="2026-01-01T00:00:04Z",
                )
            ],
        ]
    )
    audit = PagedStore(
        [
            [
                StoredAuditHistory(
                    auditId="a1",
                    ticketId=ticket_id,
                    actionType="WORK_ORDER_START",
                    actorId="staff_admin_001",
                    actorRole="administrator",
                    summary="Work order wo_1 started.",
                    createdAt="2026-01-01T00:00:02Z",
                )
            ],
            [
                StoredAuditHistory(
                    auditId="a2",
                    ticketId=ticket_id,
                    actionType="WORK_ORDER_COMPLETE",
                    actorId="staff_admin_001",
                    actorRole="administrator",
                    summary="Work order wo_2 completed.",
                    createdAt="2026-01-01T00:00:05Z",
                )
            ],
        ]
    )
    comments = PagedStore(
        [
            [
                StoredStaffComment(
                    commentId="c1",
                    ticketId=ticket_id,
                    authorStaffId="staff_admin_001",
                    text="internal",
                    mentionedStaffIds=[],
                    createdAt="2026-01-01T00:00:03Z",
                )
            ],
            [
                StoredStaffComment(
                    commentId="c2",
                    ticketId=ticket_id,
                    authorStaffId="staff_admin_001",
                    text="internal 2",
                    mentionedStaffIds=[],
                    createdAt="2026-01-01T00:00:06Z",
                )
            ],
        ]
    )
    monkeypatch.setattr(comments_module, "get_status_history_store", lambda: status)
    monkeypatch.setattr(comments_module, "get_audit_history_store", lambda: audit)
    monkeypatch.setattr(comments_module, "get_staff_comment_store", lambda: comments)

    seen = []
    cursor = None
    for _ in range(6):
        response = comments_module.staff_comment_service.timeline(
            ticket_id, principal=principal, limit=1, cursor=cursor
        )
        assert len(response.events) == 1
        seen.append(response.events[0].event_id)
        cursor = response.next_cursor
    assert seen == [
        "status:h1",
        "audit:a1",
        "comment:c1",
        "status:h2",
        "audit:a2",
        "comment:c2",
    ]
    assert cursor is None
    assert all(call[0] == 1 for call in status.calls + audit.calls + comments.calls)


def test_storage_cursor_rejects_tampering():
    event = ActivityEvent(
        eventId="audit:a1",
        eventType="WORK_ORDER_START",
        occurredAt="2026-01-01T00:00:00Z",
        details={"summary": "Work order started."},
        sourceReference="audit:a1",
    )
    cursor = comments_module._encode_storage_cursor(
        {"status": {"done": True}, "audit": {"done": True}, "comments": {"done": True}},
        {"status": [event], "audit": [], "comments": []},
    )
    tampered = f"{cursor[:-1]}{'A' if cursor[-1] != 'A' else 'B'}"
    assert comments_module._decode_storage_cursor(tampered) is None


def test_dynamo_staff_comment_store_keeps_settings_for_activity_gsi(
    dynamodb_settings,
) -> None:
    from app.database.dynamo_staff_comment_store import DynamoStaffCommentStore

    store = DynamoStaffCommentStore(dynamodb_settings)
    assert store._settings is dynamodb_settings
    items, cursor = store.list_by_ticket_id_page("tkt_missing_activity", limit=10)
    assert items == []
    assert cursor is None
