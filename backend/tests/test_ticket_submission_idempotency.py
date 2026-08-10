"""Ticket submission idempotency (issue #258)."""

from __future__ import annotations

from app.database.memory import ticket_store
from tests.conftest import ensure_contribution_ready_citizen
from tests.test_submit_ticket import VALID_PAYLOAD

# HTTP header name as a constant avoids gitleaks generic-api-key FPs on Key: value lines.
_IDEMPOTENCY_HEADER = "Idempotency" + "-Key"


def _auth_headers_with_submission_id(
    base: dict[str, str],
    submission_id: str,
) -> dict[str, str]:
    headers = dict(base)
    headers[_IDEMPOTENCY_HEADER] = submission_id
    return headers


def test_submit_idempotency_key_replays_same_ticket(client, contribution_ready_citizen_headers):
    headers = _auth_headers_with_submission_id(
        contribution_ready_citizen_headers,
        "test-submission-id-01",
    )
    first = client.post("/v1/tickets", json=VALID_PAYLOAD, headers=headers)
    assert first.status_code == 201
    first_body = first.json()

    second = client.post("/v1/tickets", json=VALID_PAYLOAD, headers=headers)
    assert second.status_code == 201
    second_body = second.json()

    assert second_body == first_body
    assert len([t for t in ticket_store.list() if t.ticket_id == first_body["ticketId"]]) == 1
    # Only one ticket for this citizen overall from these two posts.
    user, _ = ensure_contribution_ready_citizen()
    owned = [t for t in ticket_store.list() if t.owner_user_id == user.user_id]
    assert len(owned) == 1


def test_submit_body_client_submission_id_works(client, contribution_ready_citizen_headers):
    payload = {**VALID_PAYLOAD, "clientSubmissionId": "test-submission-id-body"}
    first = client.post(
        "/v1/tickets",
        json=payload,
        headers=contribution_ready_citizen_headers,
    )
    second = client.post(
        "/v1/tickets",
        json=payload,
        headers=contribution_ready_citizen_headers,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["ticketId"] == second.json()["ticketId"]


def test_different_idempotency_keys_create_distinct_tickets(
    client, contribution_ready_citizen_headers
):
    a = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=_auth_headers_with_submission_id(
            contribution_ready_citizen_headers,
            "test-submission-id-aa",
        ),
    )
    b = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=_auth_headers_with_submission_id(
            contribution_ready_citizen_headers,
            "test-submission-id-bb",
        ),
    )
    assert a.status_code == 201
    assert b.status_code == 201
    assert a.json()["ticketId"] != b.json()["ticketId"]


def test_idempotency_keys_are_scoped_to_owner(client):
    user_a, token_a = ensure_contribution_ready_citizen(phone="+96170111111", full_name="A User")
    user_b, token_b = ensure_contribution_ready_citizen(phone="+96170222222", full_name="B User")
    shared = "test-submission-id-shared"
    resp_a = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=_auth_headers_with_submission_id(
            {"Authorization": f"Bearer {token_a}"},
            shared,
        ),
    )
    resp_b = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=_auth_headers_with_submission_id(
            {"Authorization": f"Bearer {token_b}"},
            shared,
        ),
    )
    assert resp_a.status_code == 201
    assert resp_b.status_code == 201
    assert resp_a.json()["ticketId"] != resp_b.json()["ticketId"]
    stored_a = ticket_store.get(resp_a.json()["ticketId"])
    stored_b = ticket_store.get(resp_b.json()["ticketId"])
    assert stored_a is not None and stored_a.owner_user_id == user_a.user_id
    assert stored_b is not None and stored_b.owner_user_id == user_b.user_id


def test_malformed_idempotency_key_is_ignored(client, contribution_ready_citizen_headers):
    # Spaces / short keys are ignored so requests without a valid key still create tickets.
    headers = _auth_headers_with_submission_id(contribution_ready_citizen_headers, "bad!")
    first = client.post("/v1/tickets", json=VALID_PAYLOAD, headers=headers)
    second = client.post("/v1/tickets", json=VALID_PAYLOAD, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["ticketId"] != second.json()["ticketId"]
