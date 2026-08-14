"""Helpers for partial ticket attribute updates (avoids full put_item races)."""

from __future__ import annotations

from typing import Any

# StoredTicket Python field name -> DynamoDB / JSON alias
TICKET_FIELD_ALIASES: dict[str, str] = {
    "cleaned_description": "cleanedDescription",
    "ai_suggested_category": "aiSuggestedCategory",
    "ai_category_explanation": "aiCategoryExplanation",
    "ai_confidence": "aiConfidence",
    "ai_model_version": "aiModelVersion",
    "ai_processing_status": "aiProcessingStatus",
    "ai_processing_claim_token": "aiProcessingClaimToken",
    "final_category": "finalCategory",
    "category": "category",
    "category_reviewed_by": "categoryReviewedBy",
    "category_reviewed_at": "categoryReviewedAt",
    "owner_user_id": "ownerUserId",
    "public_status": "publicStatus",
    "public_description": "publicDescription",
    "public_location_label": "publicLocationLabel",
    "public_published_at": "publicPublishedAt",
    "public_image_object_key": "publicImageObjectKey",
    "image_redaction_status": "imageRedactionStatus",
    "image_redaction_generation": "imageRedactionGeneration",
    "image_redaction_claim_token": "imageRedactionClaimToken",
    "image_redaction_detector": "imageRedactionDetector",
    "image_redaction_detector_version": "imageRedactionDetectorVersion",
    "image_redaction_face_count": "imageRedactionFaceCount",
    "image_redaction_plate_count": "imageRedactionPlateCount",
    "image_redaction_completed_at": "imageRedactionCompletedAt",
    "image_redaction_reason_code": "imageRedactionReasonCode",
    "image_redaction_history": "imageRedactionHistory",
    "duplicate_group_id": "duplicateGroupId",
    "updated_at": "updatedAt",
    "updated_by": "updatedBy",
    "status": "status",
    "priority": "priority",
    "urgency_score": "urgencyScore",
    "urgency_reason": "urgencyReason",
    "department_id": "departmentId",
    "suggested_department_id": "suggestedDepartmentId",
    "assigned_worker_id": "assignedWorkerId",
    "assigned_team_id": "assignedTeamId",
}


def resolve_ticket_attr_name(field_name: str) -> str:
    try:
        return TICKET_FIELD_ALIASES[field_name]
    except KeyError as exc:
        raise KeyError(f"Unsupported ticket patch field: {field_name}") from exc


def build_update_expression(fields: dict[str, Any]) -> tuple[str, dict[str, str], dict[str, Any]]:
    """Build a DynamoDB UpdateExpression for SET/REMOVE of ticket attributes."""
    set_parts: list[str] = []
    remove_parts: list[str] = []
    names: dict[str, str] = {}
    values: dict[str, Any] = {}

    for index, (field_name, value) in enumerate(fields.items()):
        attr = resolve_ticket_attr_name(field_name)
        name_key = f"#f{index}"
        names[name_key] = attr
        if value is None:
            remove_parts.append(name_key)
            continue
        value_key = f":v{index}"
        set_parts.append(f"{name_key} = {value_key}")
        values[value_key] = value

    clauses: list[str] = []
    if set_parts:
        clauses.append("SET " + ", ".join(set_parts))
    if remove_parts:
        clauses.append("REMOVE " + ", ".join(remove_parts))
    if not clauses:
        raise ValueError("At least one field is required for a ticket patch.")
    return " ".join(clauses), names, values


def append_ticket_assignment_scope_condition(
    names: dict[str, str],
    values: dict[str, Any],
    *,
    expected_updated_at: str | None,
    expected_municipality_id: str | None,
    expected_department_id: str | None,
) -> str:
    """AND-able Dynamo condition for municipality, department, and version."""
    parts = ["attribute_exists(ticketId)"]
    for alias, attr, expected in (
        ("#tasu", "updatedAt", expected_updated_at),
        ("#tasm", "municipalityId", expected_municipality_id),
        ("#tasd", "departmentId", expected_department_id),
    ):
        names[alias] = attr
        if expected is None:
            parts.append(f"attribute_not_exists({alias})")
            continue
        value_key = f":{alias[1:]}"
        values[value_key] = expected
        parts.append(f"{alias} = {value_key}")
    return " AND ".join(parts)
