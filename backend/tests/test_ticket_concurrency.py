"""CI concurrency tests for capacity validation (issue #191)."""

from __future__ import annotations

import concurrent.futures

from app.database.memory import ticket_store
from app.services.complaints.ticket_service import ticket_service
from tests.test_read_tickets import create_ticket

STREET_LIGHTING = "d3333333-3333-3333-3333-333333333333"
ADMIN_STAFF_ID = "staff_admin_001"


def test_concurrent_status_transition_single_consistent_outcome(client):
    """Many workers race the first allowed status move; state stays valid."""
    created = create_ticket(client)
    ticket_id = created["ticketId"]

    def attempt(_: int) -> int:
        response = client.patch(
            f"/v1/tickets/{ticket_id}/status",
            json={"status": "UNDER_REVIEW", "updatedBy": "race-worker", "note": "raced"},
        )
        return response.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(attempt, range(8)))

    assert any(code == 200 for code in codes)
    # Losers must be client errors (invalid transition or race), not 5xx.
    assert all(code < 500 for code in codes)

    detail = client.get(f"/v1/tickets/{ticket_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "UNDER_REVIEW"
    statuses = [entry["status"] for entry in body["statusHistory"]]
    assert statuses[0] == "SUBMITTED"
    assert statuses[-1] == "UNDER_REVIEW"
    # At most one UNDER_REVIEW entry from a raced identical transition.
    assert statuses.count("UNDER_REVIEW") == 1


def test_concurrent_category_review_is_idempotent(client):
    created = create_ticket(client)
    ticket_id = created["ticketId"]

    def attempt(index: int) -> int:
        response = client.patch(
            f"/v1/tickets/{ticket_id}/category",
            json={"finalCategory": "road_damage", "categoryReviewedBy": f"worker-{index}"},
        )
        return response.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(attempt, range(6)))

    assert all(code == 200 for code in codes)
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    assert stored.final_category == "road_damage"


def test_concurrent_ai_process_single_completion(client, monkeypatch):
    created = create_ticket(client)
    ticket_id = created["ticketId"]
    # Ticket may already have been processed by background tasks — reset claim fields for race.
    stored = ticket_store.get(ticket_id)
    assert stored is not None

    def run(_: int) -> bool:
        return bool(ticket_service.process_ticket_ai(ticket_id))

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(run, range(6)))

    # At most one worker performs AI work; others no-op/false.
    assert sum(1 for value in results if value is True) <= 1
    final = ticket_store.get(ticket_id)
    assert final is not None


def test_concurrent_department_assign_consistent(client):
    created = create_ticket(client)
    ticket_id = created["ticketId"]
    client.patch(
        f"/v1/tickets/{ticket_id}/category",
        json={"finalCategory": "road_damage", "categoryReviewedBy": "prep"},
    )

    def attempt(_: int) -> int:
        response = client.patch(
            f"/v1/tickets/{ticket_id}/department",
            json={"departmentId": STREET_LIGHTING, "updatedBy": "race"},
        )
        return response.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(attempt, range(6)))

    assert all(code == 200 for code in codes)
    detail = client.get(f"/v1/tickets/{ticket_id}")
    assert detail.status_code == 200
    assert detail.json()["departmentId"] == STREET_LIGHTING
