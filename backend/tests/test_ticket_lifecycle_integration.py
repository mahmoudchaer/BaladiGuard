from app.database.memory import ticket_store
from app.schemas.classification import ClassificationInputs, ClassificationResult
from app.schemas.cleaning import CleaningResult
from app.services.ai_job_queue import ai_job_queue
from app.services.complaints.ticket_service import ticket_service
from tests.conftest import contribution_ready_auth_headers

ADMIN_STAFF_ID = "staff_admin_001"

VALID_LIFECYCLE_PAYLOAD = {
    "description": "Large pothole reported near the university gate causing traffic disruption.",
    "languageHint": "auto",
    "location": {
        "latitude": 33.896112,
        "longitude": 35.478419,
        "addressText": "Near AUB Main Gate, Hamra, Beirut",
        "source": "GPS",
    },
    "imageObjectKey": "reports/temp/01JZABCDEF/photo.jpg",
    "clientMetadata": {
        "platform": "ios",
        "appVersion": "0.1.0",
    },
}


def test_ticket_lifecycle_with_ai_processing_and_staff_review(client, monkeypatch):
    original_description = (
        "Overflowing garbage bins beside the school entrance are blocking pedestrians "
        "and creating a strong smell."
    )
    payload = {
        **VALID_LIFECYCLE_PAYLOAD,
        "description": original_description,
        "location": {
            **VALID_LIFECYCLE_PAYLOAD["location"],
            "addressText": "Beside the municipal school entrance, Hamra, Beirut",
        },
    }
    ai_suggestion = "waste"

    def classify(description: str, *, image_object_key: str, **_: object):
        assert description == original_description
        assert image_object_key == VALID_LIFECYCLE_PAYLOAD["imageObjectKey"]
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

    create_response = client.post(
        "/v1/tickets",
        json=payload,
        headers=contribution_ready_auth_headers(),
    )

    assert create_response.status_code == 201
    assert ai_job_queue.run_once().outcome == "succeeded"
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
    assert ticket["category"] == "PENDING_CLASSIFICATION"
    assert ticket["priority"] == "medium"
    assert ticket["ai"]["urgencyScore"] == 37
    assert ticket["ai"]["urgencyReason"] == (
        "Medium (37): critical location; public disruption or inconvenience; strong evidence."
    )
    assert ticket["ai"]["finalCategory"] is None
    assert [entry["status"] for entry in ticket["statusHistory"]] == ["SUBMITTED"]
    ai_priority_before_review = ticket["priority"]
    ai_urgency_score_before_review = ticket["ai"]["urgencyScore"]
    ai_urgency_reason_before_review = ticket["ai"]["urgencyReason"]

    review_response = client.patch(
        f"/v1/tickets/{ticket_id}/category",
        json={"finalCategory": "road_damage", "categoryReviewedBy": "staff-category-reviewer"},
    )

    assert review_response.status_code == 200
    reviewed = review_response.json()
    assert reviewed["category"] == "road_damage"
    assert reviewed["ai"]["finalCategory"] == "road_damage"
    assert reviewed["ai"]["categoryReviewedBy"] == ADMIN_STAFF_ID
    assert reviewed["ai"]["categoryReviewedAt"]
    assert reviewed["ai"]["aiSuggestedCategory"] == ai_suggestion
    assert reviewed["ai"]["originalDescription"] == original_description
    assert reviewed["priority"] == ai_priority_before_review
    assert reviewed["ai"]["urgencyScore"] == ai_urgency_score_before_review
    assert reviewed["ai"]["urgencyReason"] == ai_urgency_reason_before_review

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
    expected_status_history = [
        {
            "status": "SUBMITTED",
            "changedAt": created["createdAt"],
            "changedBy": None,
            "note": "Ticket submitted.",
        },
        {
            "status": "UNDER_REVIEW",
            "changedAt": status_body["updatedAt"],
            "changedBy": ADMIN_STAFF_ID,
            "note": "Category reviewed and ready for assignment.",
        },
    ]
    assert status_body["statusHistory"] == expected_status_history
    assert status_body["ai"]["aiSuggestedCategory"] == ai_suggestion
    assert status_body["ai"]["finalCategory"] == "road_damage"
    assert status_body["priority"] == ai_priority_before_review
    assert status_body["ai"]["urgencyScore"] == ai_urgency_score_before_review
    assert status_body["ai"]["urgencyReason"] == ai_urgency_reason_before_review

    final_read_response = client.get(f"/v1/tickets/{ticket_id}")

    assert final_read_response.status_code == 200
    final_ticket = final_read_response.json()
    assert final_ticket["status"] == "UNDER_REVIEW"
    assert final_ticket["statusHistory"] == expected_status_history
    assert final_ticket["category"] == "road_damage"
    assert final_ticket["ai"]["aiSuggestedCategory"] == ai_suggestion
    assert final_ticket["ai"]["finalCategory"] == "road_damage"
    assert final_ticket["priority"] == ai_priority_before_review
    assert final_ticket["ai"]["urgencyScore"] == ai_urgency_score_before_review
    assert final_ticket["ai"]["urgencyReason"] == ai_urgency_reason_before_review

    stored = ticket_store.get(ticket_id)
    assert stored is not None
    assert stored.description == original_description
    assert stored.original_description == original_description
    assert stored.ai_suggested_category == ai_suggestion
    assert stored.final_category == "road_damage"
