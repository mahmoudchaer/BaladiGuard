import logging
import os
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.database.memory import ticket_store
from app.main import app
from app.schemas.classification import ClassificationInputs, ClassificationResult
from app.schemas.cleaning import CleaningResult
from app.schemas.stored_ticket import PENDING_CLASSIFICATION, StoredTicket
from app.schemas.ticket import ReportContact, ReportLocation, SubmitTicketRequest
from app.services.complaints.ticket_service import ticket_service
from tests.conftest import authenticated_test_client
from tests.test_submit_ticket import VALID_PAYLOAD


def test_submission_persists_successful_ai_output_and_read_api_returns_it(
    client,
    monkeypatch,
):
    calls: list[tuple[str, str]] = []

    def classify(description: str, *, image_object_key: str, **_: object):
        calls.append((description, image_object_key))
        return ClassificationResult(
            category="road_damage",
            explanation="The report describes a pothole affecting traffic.",
            usedInputs=ClassificationInputs(description=True, image=True),
        )

    def clean(description: str, **_: object):
        return CleaningResult(
            cleanedDescription="Large pothole near the university gate is disrupting traffic.",
            usedFallback=False,
        )

    monkeypatch.setattr(ticket_service, "_classifier", classify)
    monkeypatch.setattr(ticket_service, "_description_cleaner", clean)

    response = client.post("/v1/tickets", json=VALID_PAYLOAD)

    assert response.status_code == 201
    ticket_id = response.json()["ticketId"]
    assert calls == [(VALID_PAYLOAD["description"], VALID_PAYLOAD["imageObjectKey"])]

    stored = ticket_store.get(ticket_id)
    assert stored is not None
    assert stored.description == VALID_PAYLOAD["description"]
    assert stored.original_description == VALID_PAYLOAD["description"]
    assert stored.cleaned_description == (
        "Large pothole near the university gate is disrupting traffic."
    )
    assert stored.ai_suggested_category == "road_damage"
    assert stored.ai_category_explanation == ("The report describes a pothole affecting traffic.")
    assert stored.ai_processing_status == "completed"
    assert stored.ai_model_version
    assert stored.priority == "high"
    assert stored.urgency_score is not None
    assert stored.urgency_reason
    assert stored.department_id == "d1111111-1111-1111-1111-111111111111"

    read_response = client.get(f"/v1/tickets/{ticket_id}")
    assert read_response.status_code == 200
    read_body = read_response.json()
    assert read_body["departmentId"] == "d1111111-1111-1111-1111-111111111111"
    assert read_body["department"]["name"] == "Road Maintenance"
    ai = read_body["ai"]
    assert ai["originalDescription"] == VALID_PAYLOAD["description"]
    assert ai["cleanedDescription"] == stored.cleaned_description
    assert ai["aiSuggestedCategory"] == "road_damage"
    assert ai["aiProcessingStatus"] == "completed"
    assert ai["urgencyScore"] == stored.urgency_score
    assert ai["urgencyReason"] == stored.urgency_reason


def test_provider_timeout_does_not_block_ticket_creation_or_log_report_content(
    client,
    monkeypatch,
    caplog,
):
    def timeout(*_: object, **__: object):
        raise TimeoutError("provider timed out")

    monkeypatch.setattr(ticket_service, "_classifier", timeout)
    caplog.set_level(logging.ERROR)

    response = client.post("/v1/tickets", json=VALID_PAYLOAD)

    assert response.status_code == 201
    ticket_id = response.json()["ticketId"]
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    assert stored.original_description == VALID_PAYLOAD["description"]
    assert stored.ai_processing_status == "failed"
    assert stored.cleaned_description is None
    assert stored.ai_suggested_category is None
    assert stored.priority is not None
    assert stored.urgency_score is not None
    assert stored.urgency_reason
    assert ticket_id in caplog.text
    assert "TimeoutError" in caplog.text
    assert VALID_PAYLOAD["description"] not in caplog.text


def test_classification_fallback_keeps_successful_cleaning_as_partial_success(
    client,
    monkeypatch,
):
    def fallback_classification(*_: object, **__: object):
        return ClassificationResult(
            category="PENDING_CLASSIFICATION",
            explanation="Unable to classify this report confidently.",
            usedInputs=ClassificationInputs(description=True, image=False),
            usedFallback=True,
        )

    def clean(description: str, **_: object):
        return CleaningResult(
            cleanedDescription=description,
            usedFallback=False,
        )

    monkeypatch.setattr(ticket_service, "_classifier", fallback_classification)
    monkeypatch.setattr(ticket_service, "_description_cleaner", clean)

    response = client.post("/v1/tickets", json=VALID_PAYLOAD)

    assert response.status_code == 201
    stored = ticket_store.get(response.json()["ticketId"])
    assert stored is not None
    # Cleaning succeeded, so the run is a partial success, not a failure.
    assert stored.ai_processing_status == "completed"
    assert stored.cleaned_description == VALID_PAYLOAD["description"]
    assert stored.ai_suggested_category is None
    assert stored.ai_category_explanation is None
    assert stored.category == "PENDING_CLASSIFICATION"
    assert stored.department_id is None


def test_cleaning_fallback_never_discards_a_valid_category(
    client,
    monkeypatch,
):
    def classify(*_: object, **__: object):
        return ClassificationResult(
            category="road_damage",
            explanation="The report describes damage to a public road.",
            usedInputs=ClassificationInputs(description=True, image=False),
        )

    def fallback_clean(*_: object, **__: object):
        return CleaningResult(
            cleanedDescription=None,
            usedFallback=True,
            message="Unable to clean this report description.",
        )

    monkeypatch.setattr(ticket_service, "_classifier", classify)
    monkeypatch.setattr(ticket_service, "_description_cleaner", fallback_clean)

    response = client.post("/v1/tickets", json=VALID_PAYLOAD)

    assert response.status_code == 201
    stored = ticket_store.get(response.json()["ticketId"])
    assert stored is not None
    assert stored.ai_processing_status == "completed"
    assert stored.ai_suggested_category == "road_damage"
    assert stored.ai_category_explanation == "The report describes damage to a public road."
    assert stored.cleaned_description is None
    assert stored.department_id == "d1111111-1111-1111-1111-111111111111"


def test_processing_is_failed_only_when_both_sides_fall_back(
    client,
    monkeypatch,
):
    def fallback_classification(*_: object, **__: object):
        return ClassificationResult(
            category="PENDING_CLASSIFICATION",
            explanation="Unable to classify this report confidently.",
            usedInputs=ClassificationInputs(description=True, image=False),
            usedFallback=True,
        )

    def fallback_clean(*_: object, **__: object):
        return CleaningResult(
            cleanedDescription=None,
            usedFallback=True,
            message="Unable to clean this report description.",
        )

    monkeypatch.setattr(ticket_service, "_classifier", fallback_classification)
    monkeypatch.setattr(ticket_service, "_description_cleaner", fallback_clean)

    response = client.post("/v1/tickets", json=VALID_PAYLOAD)

    assert response.status_code == 201
    stored = ticket_store.get(response.json()["ticketId"])
    assert stored is not None
    assert stored.ai_processing_status == "failed"
    assert stored.cleaned_description is None
    assert stored.ai_suggested_category is None
    assert stored.ai_category_explanation is None
    assert stored.department_id is None


def test_repeated_processing_for_same_ticket_is_a_no_op(monkeypatch):
    calls = {"classification": 0, "cleaning": 0}

    def classify(*_: object, **__: object):
        calls["classification"] += 1
        return ClassificationResult(
            category="road_damage",
            explanation="Road damage.",
            usedInputs=ClassificationInputs(description=True, image=False),
        )

    def clean(description: str, **_: object):
        calls["cleaning"] += 1
        return CleaningResult(cleanedDescription=description, usedFallback=False)

    monkeypatch.setattr(ticket_service, "_classifier", classify)
    monkeypatch.setattr(ticket_service, "_description_cleaner", clean)
    created = ticket_service.submit_ticket(SubmitTicketRequest.model_validate(VALID_PAYLOAD))

    assert ticket_service.process_ticket_ai(created.ticket_id) is True
    assert ticket_service.process_ticket_ai(created.ticket_id) is False
    assert calls == {"classification": 1, "cleaning": 1}


def test_store_claim_allows_only_one_worker_to_process(monkeypatch):
    """A second claim fails once the ticket is processing, so Bedrock runs once."""
    calls = {"classification": 0}
    claimed_statuses: list[str] = []

    def classify(*_: object, **__: object):
        calls["classification"] += 1
        stored = ticket_store.get(created.ticket_id)
        assert stored is not None
        claimed_statuses.append(stored.ai_processing_status)
        return ClassificationResult(
            category="road_damage",
            explanation="Road damage.",
            usedInputs=ClassificationInputs(description=True, image=False),
        )

    def clean(description: str, **_: object):
        return CleaningResult(cleanedDescription=description, usedFallback=False)

    monkeypatch.setattr(ticket_service, "_classifier", classify)
    monkeypatch.setattr(ticket_service, "_description_cleaner", clean)
    created = ticket_service.submit_ticket(SubmitTicketRequest.model_validate(VALID_PAYLOAD))

    first_claim = ticket_store.claim_ai_processing(
        created.ticket_id,
        "2026-07-18T00:00:00Z",
    )
    assert first_claim is not None
    assert first_claim.ai_processing_status == "processing"
    assert ticket_store.claim_ai_processing(created.ticket_id, "2026-07-18T00:00:01Z") is None

    # Release and let process_ticket_ai claim + finish for the happy path.
    released = ticket_store.release_ai_processing_claim(
        created.ticket_id,
        "2026-07-18T00:00:02Z",
    )
    assert released is not None
    assert released.ai_processing_status == "pending"
    assert ticket_service.process_ticket_ai(created.ticket_id) is True
    assert calls["classification"] == 1
    assert claimed_statuses == ["processing"]
    assert ticket_service.process_ticket_ai(created.ticket_id) is False


def test_recover_pending_ai_tickets_sweeps_stuck_tickets(monkeypatch):
    """A ticket left `pending` (e.g. worker crash) is recovered by the startup sweep."""
    calls = {"classification": 0}

    def classify(*_: object, **__: object):
        calls["classification"] += 1
        return ClassificationResult(
            category="road_damage",
            explanation="Road damage.",
            usedInputs=ClassificationInputs(description=True, image=False),
        )

    def clean(description: str, **_: object):
        return CleaningResult(cleanedDescription=description, usedFallback=False)

    monkeypatch.setattr(ticket_service, "_classifier", classify)
    monkeypatch.setattr(ticket_service, "_description_cleaner", clean)

    # Submitting through the service (not the API) leaves the ticket pending because
    # no background task runs, simulating a crash before processing.
    created = ticket_service.submit_ticket(SubmitTicketRequest.model_validate(VALID_PAYLOAD))
    stored = ticket_store.get(created.ticket_id)
    assert stored is not None
    assert stored.ai_processing_status == "pending"

    recovered = ticket_service.recover_pending_ai_tickets()

    assert recovered == 1
    assert calls["classification"] == 1
    stored = ticket_store.get(created.ticket_id)
    assert stored is not None
    assert stored.ai_processing_status == "completed"

    # A second sweep finds nothing to do.
    assert ticket_service.recover_pending_ai_tickets() == 0


def test_recover_pending_ai_tickets_releases_stuck_processing_claims(monkeypatch):
    """A stale `processing` claim (past the timeout) is released and completed."""
    calls = {"classification": 0}

    def classify(*_: object, **__: object):
        calls["classification"] += 1
        return ClassificationResult(
            category="road_damage",
            explanation="Road damage.",
            usedInputs=ClassificationInputs(description=True, image=False),
        )

    def clean(description: str, **_: object):
        return CleaningResult(cleanedDescription=description, usedFallback=False)

    monkeypatch.setattr(ticket_service, "_classifier", classify)
    monkeypatch.setattr(ticket_service, "_description_cleaner", clean)

    created = ticket_service.submit_ticket(SubmitTicketRequest.model_validate(VALID_PAYLOAD))
    # Far in the past so the claim is older than AI_PROCESSING_CLAIM_TIMEOUT_SECONDS.
    claimed = ticket_store.claim_ai_processing(created.ticket_id, "2020-01-01T00:00:00Z")
    assert claimed is not None
    assert claimed.ai_processing_status == "processing"

    recovered = ticket_service.recover_pending_ai_tickets()

    assert recovered == 1
    assert calls["classification"] == 1
    stored = ticket_store.get(created.ticket_id)
    assert stored is not None
    assert stored.ai_processing_status == "completed"


def test_recover_pending_ai_tickets_skips_fresh_processing_claims(monkeypatch):
    """A fresh processing claim must not be stolen during multi-worker startup."""
    calls = {"classification": 0}

    def classify(*_: object, **__: object):
        calls["classification"] += 1
        return ClassificationResult(
            category="road_damage",
            explanation="Road damage.",
            usedInputs=ClassificationInputs(description=True, image=False),
        )

    def clean(description: str, **_: object):
        return CleaningResult(cleanedDescription=description, usedFallback=False)

    monkeypatch.setattr(ticket_service, "_classifier", classify)
    monkeypatch.setattr(ticket_service, "_description_cleaner", clean)

    created = ticket_service.submit_ticket(SubmitTicketRequest.model_validate(VALID_PAYLOAD))
    claimed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    claimed = ticket_store.claim_ai_processing(created.ticket_id, claimed_at)
    assert claimed is not None
    assert claimed.ai_processing_status == "processing"

    recovered = ticket_service.recover_pending_ai_tickets()

    assert recovered == 0
    assert calls["classification"] == 0
    stored = ticket_store.get(created.ticket_id)
    assert stored is not None
    assert stored.ai_processing_status == "processing"
    assert stored.updated_at == claimed_at


def test_submission_ai_output_persists_with_moto_dynamodb(
    dynamodb_settings: Settings,
) -> None:
    """Moto-backed DynamoDB store test with the stubbed classifier/cleaner.

    This verifies the persistence wiring only. It does not exercise real Bedrock or
    real DynamoDB; see the opt-in live tests for Bedrock and cloud DynamoDB checks.
    """
    store = DynamoTicketStore(dynamodb_settings)
    original_store = ticket_service._store
    ticket_service._store = store

    try:
        response = TestClient(app).post("/v1/tickets", json=VALID_PAYLOAD)

        assert response.status_code == 201
        stored = store.get(response.json()["ticketId"])
        assert stored is not None
        assert stored.original_description == VALID_PAYLOAD["description"]
        assert stored.cleaned_description == VALID_PAYLOAD["description"]
        assert stored.ai_suggested_category == "road_damage"
        assert stored.ai_processing_status == "completed"
    finally:
        ticket_service._store = original_store


def test_claim_ai_processing_is_conditional_in_moto_dynamodb(
    dynamodb_settings: Settings,
) -> None:
    store = DynamoTicketStore(dynamodb_settings)
    created_at = "2026-07-18T00:00:00Z"
    ticket = StoredTicket(
        ticketId="tkt_claim_001",
        ticketNumber="BG-2026-8801",
        trackingCode="CL01AIM",
        description="Large pothole near the university gate.",
        contact=ReportContact(name="Test User", phone="+96170000000"),
        location=ReportLocation(
            latitude=33.89,
            longitude=35.50,
            addressText="Hamra, Beirut",
            source="MANUAL",
        ),
        imageObjectKey="reports/mock/claim.jpg",
        status="SUBMITTED",
        category=PENDING_CLASSIFICATION,
        aiProcessingStatus="pending",
        createdAt=created_at,
        updatedAt=created_at,
    )
    store.save(ticket)

    first = store.claim_ai_processing("tkt_claim_001", "2026-07-18T00:00:01Z")
    second = store.claim_ai_processing("tkt_claim_001", "2026-07-18T00:00:02Z")

    assert first is not None
    assert first.ai_processing_status == "processing"
    assert second is None
    loaded = store.get("tkt_claim_001")
    assert loaded is not None
    assert loaded.ai_processing_status == "processing"

    released = store.release_ai_processing_claim("tkt_claim_001", "2026-07-18T00:00:03Z")
    assert released is not None
    assert released.ai_processing_status == "pending"


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_AI") != "1",
    reason="Live Bedrock test; set RUN_LIVE_AI=1 with AWS credentials to run.",
)
def test_live_submission_processes_real_ai(client, monkeypatch):
    """Opt-in Bedrock wiring check (memory store; no cloud DynamoDB).

    For real Bedrock → cloud DynamoDB → read, use
    ``test_live_submission_persists_real_ai_to_cloud_dynamodb`` with
    ``RUN_LIVE_AI=1 RUN_LIVE_DYNAMODB=1``.
    """
    from app.services.ai.classify import classify_complaint
    from app.services.ai.clean import clean_report_description

    monkeypatch.setattr(ticket_service, "_classifier", classify_complaint)
    monkeypatch.setattr(ticket_service, "_description_cleaner", clean_report_description)

    response = client.post("/v1/tickets", json=VALID_PAYLOAD)

    assert response.status_code == 201
    stored = ticket_store.get(response.json()["ticketId"])
    assert stored is not None
    assert stored.original_description == VALID_PAYLOAD["description"]
    assert stored.ai_processing_status in {"completed", "failed"}
    if stored.ai_processing_status == "completed":
        assert stored.cleaned_description or stored.ai_suggested_category


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_AI") != "1" or os.environ.get("RUN_LIVE_DYNAMODB") != "1",
    reason=(
        "Live Bedrock + cloud DynamoDB test; set RUN_LIVE_AI=1 RUN_LIVE_DYNAMODB=1 "
        "with AWS credentials and provisioned tables to run."
    ),
)
def test_live_submission_persists_real_ai_to_cloud_dynamodb(monkeypatch):
    """Opt-in end-to-end check: real Bedrock output persisted on real DynamoDB."""
    from app.config import get_settings
    from app.database.dynamo_status_history_store import DynamoStatusHistoryStore
    from app.services.ai.classify import classify_complaint
    from app.services.ai.clean import clean_report_description

    original_backend = os.environ.get("DATABASE_BACKEND")
    original_endpoint = os.environ.get("DYNAMODB_ENDPOINT_URL")
    os.environ["DATABASE_BACKEND"] = "dynamodb"
    os.environ.pop("DYNAMODB_ENDPOINT_URL", None)
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.use_dynamodb
    assert settings.dynamodb_endpoint_url is None

    store = DynamoTicketStore(settings)
    history_store = DynamoStatusHistoryStore(settings)
    original_store = ticket_service._store
    original_history = ticket_service._history_store
    ticket_service._store = store
    ticket_service._history_store = history_store
    monkeypatch.setattr(ticket_service, "_classifier", classify_complaint)
    monkeypatch.setattr(ticket_service, "_description_cleaner", clean_report_description)

    try:
        response = TestClient(app).post("/v1/tickets", json=VALID_PAYLOAD)
        assert response.status_code == 201
        ticket_id = response.json()["ticketId"]

        stored = store.get(ticket_id)
        assert stored is not None
        assert stored.original_description == VALID_PAYLOAD["description"]
        assert stored.ai_processing_status in {"completed", "failed"}
        if stored.ai_processing_status == "completed":
            assert stored.cleaned_description or stored.ai_suggested_category

        read_response = authenticated_test_client().get(f"/v1/tickets/{ticket_id}")
        assert read_response.status_code == 200
        ai = read_response.json()["ai"]
        assert ai["originalDescription"] == VALID_PAYLOAD["description"]
        assert ai["aiProcessingStatus"] == stored.ai_processing_status
    finally:
        ticket_service._store = original_store
        ticket_service._history_store = original_history
        if original_backend is None:
            os.environ.pop("DATABASE_BACKEND", None)
        else:
            os.environ["DATABASE_BACKEND"] = original_backend
        if original_endpoint is None:
            os.environ.pop("DYNAMODB_ENDPOINT_URL", None)
        else:
            os.environ["DYNAMODB_ENDPOINT_URL"] = original_endpoint
        get_settings.cache_clear()
        os.environ["DATABASE_BACKEND"] = "memory"
        get_settings.cache_clear()
