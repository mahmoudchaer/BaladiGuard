"""Ticket submission idempotency (issue #258)."""

from __future__ import annotations

from app.database.memory import ticket_store
from tests.conftest import ensure_contribution_ready_citizen
from tests.test_submit_ticket import VALID_PAYLOAD


def test_submit_idempotency_key_replays_same_ticket(client, contribution_ready_citizen_headers):
    headers = {
        **contribution_ready_citizen_headers,
        "Idempotency-Key": "retry-key-001-abc",
    }
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
    payload = {**VALID_PAYLOAD, "clientSubmissionId": "body-key-xyz-123"}
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
        headers={**contribution_ready_citizen_headers, "Idempotency-Key": "key-aaaaaa-01"},
    )
    b = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers={**contribution_ready_citizen_headers, "Idempotency-Key": "key-bbbbbb-02"},
    )
    assert a.status_code == 201
    assert b.status_code == 201
    assert a.json()["ticketId"] != b.json()["ticketId"]


def test_idempotency_keys_are_scoped_to_owner(client):
    user_a, token_a = ensure_contribution_ready_citizen(phone="+96170111111", full_name="A User")
    user_b, token_b = ensure_contribution_ready_citizen(phone="+96170222222", full_name="B User")
    shared = "shared-key-abcdefgh"
    resp_a = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": shared},
    )
    resp_b = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers={"Authorization": f"Bearer {token_b}", "Idempotency-Key": shared},
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
    first = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers={**contribution_ready_citizen_headers, "Idempotency-Key": "bad!"},
    )
    second = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers={**contribution_ready_citizen_headers, "Idempotency-Key": "bad!"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["ticketId"] != second.json()["ticketId"]
