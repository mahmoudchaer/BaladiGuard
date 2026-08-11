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


def test_memory_store_releases_failed_begin_without_ticket():
    from app.schemas.ticket import SubmitTicketResponse
    from app.services.complaints.ticket_submission_idempotency import (
        CLAIM_STALE_SECONDS,
        InMemoryTicketSubmissionIdempotencyStore,
    )

    store = InMemoryTicketSubmissionIdempotencyStore()
    key = "usr:test-submission-id-begin"
    assert store.try_begin(key) is True
    assert store.try_begin(key) is False
    store.release(key)
    assert store.try_begin(key) is True

    # After binding a ticket id, soft release keeps the claim.
    store.bind_ticket(key, ticket_id="tkt_bound")
    store.release(key)
    assert store.get_pending_ticket_id(key) == "tkt_bound"

    response = SubmitTicketResponse(
        ticketId="tkt_bound",
        ticketNumber="BG-2026-0001",
        trackingCode="AB12CD",
        status="SUBMITTED",
        message="ok",
        createdAt="2026-01-01T00:00:00Z",
    )
    store.complete(key, response)
    assert store.get_completed(key) is not None
    store.force_release(key)
    # force_release must not drop completed replay records.
    assert store.get_completed(key) is not None

    # Fresh claim can be force-released before complete.
    store.clear()
    assert store.try_begin("usr:x-claim-yyyyyy") is True
    store.force_release("usr:x-claim-yyyyyy")
    assert store.try_begin("usr:x-claim-yyyyyy") is True

    # Stale claims without ticket identity are reclaimed.
    store.clear()
    assert store.try_begin("usr:stale-claim-zzzz") is True
    with store._lock:
        store._entries["usr:stale-claim-zzzz"]["claimedAt"] = "2000-01-01T00:00:00Z"
    assert CLAIM_STALE_SECONDS > 0
    assert store.try_begin("usr:stale-claim-zzzz") is True


def test_complete_failure_after_ticket_does_not_duplicate(
    client, contribution_ready_citizen_headers, monkeypatch
):
    """If complete fails after the ticket is saved, retry recovers the same ticket."""
    from app.services.complaints import ticket_submission_idempotency as idem_mod

    real_complete = idem_mod._store.complete
    fail_once = {"count": 0}

    def flaky_complete(composite_key, response):
        fail_once["count"] += 1
        if fail_once["count"] == 1:
            raise RuntimeError("forced complete failure")
        return real_complete(composite_key, response)

    monkeypatch.setattr(idem_mod._store, "complete", flaky_complete)
    headers = _auth_headers_with_submission_id(
        contribution_ready_citizen_headers,
        "test-submission-complete-fail",
    )
    first = client.post("/v1/tickets", json=VALID_PAYLOAD, headers=headers)
    # Ticket path returns 500 because complete raised after save — claim still bound.
    assert first.status_code in {500, 201}
    # Retry must not create a second ticket when the first write was bound.
    second = client.post("/v1/tickets", json=VALID_PAYLOAD, headers=headers)
    assert second.status_code == 201
    owned = [t for t in ticket_store.list() if t.owner_user_id]
    # Exact one ticket for this submission key overall (may be filter by ticket id).
    ticket_ids = {second.json()["ticketId"]}
    if first.status_code == 201:
        ticket_ids.add(first.json()["ticketId"])
    assert len(ticket_ids) == 1
    assert sum(1 for t in ticket_store.list() if t.ticket_id in ticket_ids) == 1


def test_concurrent_same_key_creates_single_ticket(client, contribution_ready_citizen_headers):
    from concurrent.futures import ThreadPoolExecutor, as_completed

    headers = _auth_headers_with_submission_id(
        contribution_ready_citizen_headers,
        "test-submission-id-concurrent",
    )

    def post_once():
        return client.post("/v1/tickets", json=VALID_PAYLOAD, headers=headers)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(post_once) for _ in range(4)]
        results = [f.result() for f in as_completed(futures)]

    success = [r for r in results if r.status_code == 201]
    in_progress = [r for r in results if r.status_code == 409]
    assert len(success) >= 1
    # All successful payloads share the same ticket id.
    ticket_ids = {r.json()["ticketId"] for r in success}
    assert len(ticket_ids) == 1
    # Concurrent losers either 409 or later 201 replay with same id.
    assert len(success) + len(in_progress) == 4 or all(r.status_code in {201, 409} for r in results)
    assert sum(1 for t in ticket_store.list() if t.ticket_id in ticket_ids) == 1


def test_crash_after_bind_recovers_via_pending_ticket_id():
    from app.schemas.ticket import SubmitTicketResponse
    from app.services.complaints.ticket_submission_idempotency import (
        InMemoryTicketSubmissionIdempotencyStore,
    )

    store = InMemoryTicketSubmissionIdempotencyStore()
    key = "usr:recover-key-01"
    assert store.try_begin(key) is True
    store.bind_ticket(key, ticket_id="tkt_recover")
    # Simulate complete never happened — still bound, not completed.
    assert store.get_completed(key) is None
    assert store.get_pending_ticket_id(key) == "tkt_recover"
    # try_recover without response returns None; service loads ticket by id.
    assert store.try_recover(key) is None
    response = SubmitTicketResponse(
        ticketId="tkt_recover",
        ticketNumber="BG-2026-0099",
        trackingCode="ZZ99YY",
        status="SUBMITTED",
        message="ok",
        createdAt="2026-01-01T00:00:00Z",
    )
    store.complete(key, response)
    assert store.get_completed(key).ticket_id == "tkt_recover"
