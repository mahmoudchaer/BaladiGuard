import logging

from fastapi.testclient import TestClient

from app.config import Settings
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.database.memory import ticket_store
from app.main import app
from app.schemas.classification import ClassificationInputs, ClassificationResult
from app.schemas.cleaning import CleaningResult
from app.schemas.ticket import SubmitTicketRequest
from app.services.complaints.ticket_service import ticket_service
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

    read_response = client.get(f"/v1/tickets/{ticket_id}")
    assert read_response.status_code == 200
    ai = read_response.json()["ai"]
    assert ai["originalDescription"] == VALID_PAYLOAD["description"]
    assert ai["cleanedDescription"] == stored.cleaned_description
    assert ai["aiSuggestedCategory"] == "road_damage"
    assert ai["aiProcessingStatus"] == "completed"


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
    assert ticket_id in caplog.text
    assert "TimeoutError" in caplog.text
    assert VALID_PAYLOAD["description"] not in caplog.text


def test_malformed_ai_output_records_failed_status_and_keeps_partial_success(
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
    assert stored.ai_processing_status == "failed"
    assert stored.cleaned_description == VALID_PAYLOAD["description"]
    assert stored.ai_suggested_category is None
    assert stored.ai_category_explanation is None


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


def test_submission_ai_output_persists_with_dynamodb(
    dynamodb_settings: Settings,
) -> None:
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
