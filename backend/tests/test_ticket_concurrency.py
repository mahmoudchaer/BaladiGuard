"""CI concurrency tests for capacity validation (issue #191)."""

from __future__ import annotations

import concurrent.futures

from app.database.memory import ticket_store
from app.schemas.classification import ClassificationInputs, ClassificationResult
from app.schemas.cleaning import CleaningResult
from app.schemas.ticket import ReportContact, SubmitTicketRequest
from app.services.complaints.ticket_service import ticket_service
from tests.test_read_tickets import create_ticket
from tests.test_submit_ticket import EXPECTED_CONTACT, VALID_PAYLOAD

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


def test_concurrent_ai_process_single_completion(monkeypatch):
    """Exactly one worker completes AI; setup is deterministically pending (no background)."""
    classify_calls = {"count": 0}

    def classify(*_: object, **__: object) -> ClassificationResult:
        classify_calls["count"] += 1
        return ClassificationResult(
            category="road_damage",
            explanation="Concurrent race test classification.",
            usedInputs=ClassificationInputs(description=True, image=False),
        )

    def clean(description: str, **_: object) -> CleaningResult:
        return CleaningResult(cleanedDescription=description, usedFallback=False)

    monkeypatch.setattr(ticket_service, "_classifier", classify)
    monkeypatch.setattr(ticket_service, "_description_cleaner", clean)

    # Service submit leaves AI status pending (no FastAPI BackgroundTasks).
    created = ticket_service.submit_ticket(
        SubmitTicketRequest.model_validate(VALID_PAYLOAD),
        owner_user_id="usr_ai_race_owner",
        contact=ReportContact.model_validate(EXPECTED_CONTACT),
    )
    pending = ticket_store.get(created.ticket_id)
    assert pending is not None
    assert pending.ai_processing_status == "pending"

    def run(_: int) -> bool:
        return bool(ticket_service.process_ticket_ai(created.ticket_id))

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, range(8)))

    winners = sum(1 for value in results if value is True)
    assert winners == 1, (
        f"expected exactly one AI completion, got winners={winners} results={results}"
    )
    assert classify_calls["count"] == 1

    final = ticket_store.get(created.ticket_id)
    assert final is not None
    assert final.ai_processing_status == "completed"
    assert final.ai_suggested_category == "road_damage"
    assert final.cleaned_description == VALID_PAYLOAD["description"]

    # Further workers must no-op after terminal status.
    assert ticket_service.process_ticket_ai(created.ticket_id) is False


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
