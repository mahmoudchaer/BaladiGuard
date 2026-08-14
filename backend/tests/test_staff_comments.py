from app.database.memory import ticket_store
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
