from app.schemas.ticket_response import TicketResponse


def test_ticket_response_accepts_core_staff_read_shape():
    ticket = TicketResponse.model_validate(
        {
            "ticketId": "tkt_11111111111111111111111111111111",
            "ticketNumber": "BG-2026-0001",
            "trackingCode": "AB12CD",
            "description": "Large pothole causing traffic near the university entrance.",
            "category": "road_damage",
            "priority": "high",
            "status": "IN_PROGRESS",
            "location": {
                "latitude": 33.896112,
                "longitude": 35.478419,
                "addressText": "Near AUB Main Gate, Hamra, Beirut",
                "source": "PLACEHOLDER",
            },
            "imageReferences": [
                {
                    "objectKey": "reports/mock/pothole-aub-gate.jpg",
                    "contentType": "image/jpeg",
                }
            ],
            "department": {
                "departmentId": "d1111111-1111-1111-1111-111111111111",
                "name": "Roads",
            },
            "createdAt": "2026-08-12T09:30:00Z",
            "updatedAt": "2026-08-12T11:30:00Z",
        }
    )

    assert ticket.ticket_id == "tkt_11111111111111111111111111111111"
    assert ticket.image_references[0].object_key == "reports/mock/pothole-aub-gate.jpg"
    assert ticket.department is not None
    assert ticket.department.department_id == "d1111111-1111-1111-1111-111111111111"


def test_ticket_response_accepts_optional_ai_history_and_duplicate_fields():
    ticket = TicketResponse.model_validate(
        {
            "ticketId": "tkt_55555555555555555555555555555555",
            "trackingCode": "ZX98YU",
            "description": "Garbage bags accumulating beside the same sidewalk.",
            "category": "waste",
            "priority": "medium",
            "status": "SUBMITTED",
            "location": {
                "latitude": 33.89382,
                "longitude": 35.5018,
                "addressText": "Hamra Street, Beirut",
                "source": "PLACEHOLDER",
            },
            "imageReferences": [{"objectKey": "reports/mock/garbage-hamra-duplicate.jpg"}],
            "department": None,
            "createdAt": "2026-08-12T09:45:00Z",
            "updatedAt": None,
            "ai": {
                "originalDescription": "Garbage bags accumulating beside the same sidewalk.",
                "cleanedDescription": "Garbage bags are accumulating beside the sidewalk.",
                "aiSuggestedCategory": "waste",
                "aiCategoryExplanation": "Overflowing garbage bins and odor.",
                "aiProcessingStatus": "completed",
                "suggestedCategory": "waste",
                "urgencyScore": 50,
                "urgencyReason": "Public hygiene concern in a high-traffic area.",
                "summary": "Waste accumulation on Hamra Street.",
            },
            "statusHistory": [
                {
                    "status": "SUBMITTED",
                    "changedAt": "2026-08-12T09:45:00Z",
                    "changedBy": "system",
                }
            ],
            "duplicateGroup": {
                "duplicateGroupId": "99999999-9999-9999-9999-999999999999",
                "ticketIds": [
                    "tkt_22222222222222222222222222222222",
                    "tkt_55555555555555555555555555555555",
                ],
                "canonicalTicketId": "tkt_22222222222222222222222222222222",
            },
            "duplicateSuggestions": [
                {
                    "ticketId": "tkt_22222222222222222222222222222222",
                    "ticketNumber": "BG-2026-0002",
                    "distanceMeters": 7.25,
                    "status": "IN_PROGRESS",
                    "category": "waste",
                    "score": 0.98,
                    "categoryMatch": "same",
                }
            ],
        }
    )

    assert ticket.ai is not None
    assert ticket.ai.ai_suggested_category == "waste"
    assert ticket.ai.suggested_category == "waste"
    assert ticket.ai.urgency_score == 50
    assert ticket.status_history is not None
    assert ticket.status_history[0].changed_by == "system"
    assert ticket.duplicate_group is not None
    assert ticket.duplicate_group.duplicate_group_id == "99999999-9999-9999-9999-999999999999"
    assert ticket.duplicate_suggestions[0].ticket_id == "tkt_22222222222222222222222222222222"
    assert ticket.duplicate_suggestions[0].distance_meters == 7.25


def test_ticket_response_accepts_critical_priority():
    ticket = TicketResponse.model_validate(
        {
            "ticketId": "tkt_critical",
            "trackingCode": "CRIT01",
            "description": "Exposed electrical wires beside a school gate.",
            "category": "public_facilities",
            "priority": "critical",
            "status": "SUBMITTED",
            "location": {
                "latitude": 33.89382,
                "longitude": 35.5018,
                "addressText": "School gate, Beirut",
                "source": "GPS",
            },
            "imageReferences": [{"objectKey": "reports/mock/wires.jpg"}],
            "department": None,
            "createdAt": "2026-08-12T09:45:00Z",
            "updatedAt": None,
            "ai": {
                "urgencyScore": 75,
                "urgencyReason": "Critical (75): immediate safety danger; critical location.",
            },
        }
    )

    assert ticket.priority == "critical"
    assert ticket.ai is not None
    assert ticket.ai.urgency_score == 75
