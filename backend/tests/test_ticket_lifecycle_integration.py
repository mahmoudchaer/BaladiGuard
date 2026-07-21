from app.database.memory import ticket_store
from app.schemas.classification import ClassificationInputs, ClassificationResult
from app.schemas.cleaning import CleaningResult
from app.services.complaints.ticket_service import ticket_service
from tests.test_submit_ticket import VALID_PAYLOAD


def test_ticket_lifecycle_with_ai_processing_and_staff_review(client, monkeypatch):
    original_description = (
        "Overflowing garbage bins beside the school entrance are blocking pedestrians "
        "and creating a strong smell."
    )
    payload = {**VALID_PAYLOAD, "description": original_description}
    ai_suggestion = "waste"

    def classify(description: str, *, image_object_key: str, **_: object):
        assert description == original_description
        assert image_object_key == VALID_PAYLOAD["imageObjectKey"]
        return ClassificationResult(
            category=ai_suggestion,
            explanation="The report describes unmanaged municipal waste.",
            usedInputs=ClassificationInputs(description=True, image=True),
        )

    def clean(description: str, **_: object):
        assert description == original_description
        return CleaningResult(
            cleanedDescription=(
                "Overflowing garbage bins near the school entrance are blocking pedestrians."
            ),
            usedFallback=False,
        )

    monkeypatch.setattr(ticket_service, "_classifier", classify)
    monkeypatch.setattr(ticket_service, "_description_cleaner", clean)

    create_response = client.post("/v1/tickets", json=payload)

    assert create_response.status_code == 201
    created = create_response.json()
    ticket_id = created["ticketId"]

    read_response = client.get(f"/v1/tickets/{ticket_id}")

    assert read_response.status_code == 200
    ticket = read_response.json()
    assert ticket["ticketId"] == ticket_id
    assert ticket["description"] == original_description
    assert ticket["ai"]["originalDescription"] == original_description
    assert ticket["ai"]["cleanedDescription"] == (
        "Overflowing garbage bins near the school entrance are blocking pedestrians."
    )
    assert ticket["ai"]["aiSuggestedCategory"] == ai_suggestion
    assert ticket["ai"]["aiCategoryExplanation"] == (
        "The report describes unmanaged municipal waste."
    )
    assert ticket["ai"]["aiProcessingStatus"] == "completed"
    assert ticket["ai"]["aiModelVersion"]
    assert ticket["ai"]["urgencyScore"] is not None
    assert ticket["ai"]["urgencyReason"]
    assert ticket["category"] == "PENDING_CLASSIFICATION"
    assert ticket["ai"]["finalCategory"] is None
    assert [entry["status"] for entry in ticket["statusHistory"]] == ["SUBMITTED"]

    review_response = client.patch(
        f"/v1/tickets/{ticket_id}/category",
        json={"finalCategory": "road_damage", "categoryReviewedBy": "staff-category-reviewer"},
    )

    assert review_response.status_code == 200
    reviewed = review_response.json()
    assert reviewed["category"] == "road_damage"
    assert reviewed["ai"]["finalCategory"] == "road_damage"
    assert reviewed["ai"]["categoryReviewedBy"] == "staff-category-reviewer"
    assert reviewed["ai"]["categoryReviewedAt"]
    assert reviewed["ai"]["aiSuggestedCategory"] == ai_suggestion
    assert reviewed["ai"]["originalDescription"] == original_description

    status_response = client.patch(
        f"/v1/tickets/{ticket_id}/status",
        json={
            "status": "UNDER_REVIEW",
            "updatedBy": "staff-status-reviewer",
            "note": "Category reviewed and ready for assignment.",
        },
    )

    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["status"] == "UNDER_REVIEW"
    assert status_body["statusHistory"] == [
        {
            "status": "SUBMITTED",
            "changedAt": created["createdAt"],
            "changedBy": None,
            "note": "Ticket submitted.",
        },
        {
            "status": "UNDER_REVIEW",
            "changedAt": status_body["updatedAt"],
            "changedBy": "staff-status-reviewer",
            "note": "Category reviewed and ready for assignment.",
        },
    ]
    assert status_body["ai"]["aiSuggestedCategory"] == ai_suggestion
    assert status_body["ai"]["finalCategory"] == "road_damage"

    stored = ticket_store.get(ticket_id)
    assert stored is not None
    assert stored.description == original_description
    assert stored.original_description == original_description
    assert stored.ai_suggested_category == ai_suggestion
    assert stored.final_category == "road_damage"


def test_submission_succeeds_and_records_failed_ai_processing(client, monkeypatch):
    original_description = VALID_PAYLOAD["description"]

    def classify(*_: object, **__: object):
        raise TimeoutError("AI provider timed out")

    monkeypatch.setattr(ticket_service, "_classifier", classify)

    create_response = client.post("/v1/tickets", json=VALID_PAYLOAD)

    assert create_response.status_code == 201
    ticket_id = create_response.json()["ticketId"]

    read_response = client.get(f"/v1/tickets/{ticket_id}")

    assert read_response.status_code == 200
    ticket = read_response.json()
    assert ticket["description"] == original_description
    assert ticket["ai"]["originalDescription"] == original_description
    assert ticket["ai"]["aiProcessingStatus"] == "failed"
    assert ticket["ai"]["cleanedDescription"] is None
    assert ticket["ai"]["aiSuggestedCategory"] is None
    assert ticket["ai"]["urgencyScore"] is not None
    assert ticket["ai"]["urgencyReason"]


def test_ticket_lifecycle_rejects_invalid_lookup_and_invalid_status(client):
    missing_response = client.get("/v1/tickets/tkt_missing")

    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "TICKET_NOT_FOUND"

    create_response = client.post("/v1/tickets", json=VALID_PAYLOAD)
    assert create_response.status_code == 201
    ticket_id = create_response.json()["ticketId"]

    invalid_status_response = client.patch(
        f"/v1/tickets/{ticket_id}/status",
        json={"status": "DONE"},
    )

    assert invalid_status_response.status_code == 400
    body = invalid_status_response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == "status" for detail in body["error"]["details"])
