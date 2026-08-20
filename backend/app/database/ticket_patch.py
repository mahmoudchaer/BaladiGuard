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
    "image_redaction_candidate_object_key": "imageRedactionCandidateObjectKey",
    "image_redaction_candidate_revision": "imageRedactionCandidateRevision",
    "image_redaction_regions": "imageRedactionRegions",
    "content_safety_status": "contentSafetyStatus",
    "content_safety_generation": "contentSafetyGeneration",
    "content_safety_claim_token": "contentSafetyClaimToken",
    "content_safety_reason_code": "contentSafetyReasonCode",
    "content_safety_severity": "contentSafetySeverity",
    "content_safety_text_model": "contentSafetyTextModel",
    "content_safety_image_labels": "contentSafetyImageLabels",
    "authenticity_score": "authenticityScore",
    "authenticity_model": "authenticityModel",
    "authenticity_model_version": "authenticityModelVersion",
    "authenticity_signals": "authenticitySignals",
    "content_safety_completed_at": "contentSafetyCompletedAt",
    "content_safety_staff_note": "contentSafetyStaffNote",
    "content_safety_history": "contentSafetyHistory",
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
    "active_work_order_id": "activeWorkOrderId",
    "resolution_reason_code": "resolutionReasonCode",
    "resolution_note": "resolutionNote",
    "resolved_at": "resolvedAt",
    "resolved_by": "resolvedBy",
    "closure_reason_code": "closureReasonCode",
    "closure_note": "closureNote",
    "closed_at": "closedAt",
    "closed_by": "closedBy",
    "resolution_feedback_status": "resolutionFeedbackStatus",
    "resolution_feedback_note": "resolutionFeedbackNote",
    "resolution_feedback_submitted_at": "resolutionFeedbackSubmittedAt",
    "resolution_feedback_review_status": "resolutionFeedbackReviewStatus",
    "resolution_feedback_reviewed_at": "resolutionFeedbackReviewedAt",
    "resolution_feedback_reviewed_by": "resolutionFeedbackReviewedBy",
    "resolution_feedback_review_action": "resolutionFeedbackReviewAction",
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


def append_ticket_access_scope_condition(
    names: dict[str, str],
    values: dict[str, Any],
    *,
    expected_municipality_id: str | None,
    expected_department_id: str | None,
) -> str:
    """AND-able Dynamo condition for the municipality/department used at authorization."""
    parts: list[str] = []
    for alias, attr, expected in (
        ("#rsm", "municipalityId", expected_municipality_id),
        ("#rsd", "departmentId", expected_department_id),
    ):
        names[alias] = attr
        if expected is None:
            parts.append(f"attribute_not_exists({alias})")
            continue
        value_key = f":{alias[1:]}"
        values[value_key] = expected
        parts.append(f"{alias} = {value_key}")
    return " AND ".join(parts)


def append_redaction_review_condition(
    names: dict[str, str],
    values: dict[str, Any],
    *,
    expected_status: str,
    expected_generation: int,
    expected_candidate_revision: int,
    expected_municipality_id: str | None,
    expected_department_id: str | None,
) -> str:
    """Conditional write for a staff redaction decision against one candidate snapshot."""
    names.update(
        {
            "#rs": "imageRedactionStatus",
            "#rg": "imageRedactionGeneration",
            "#rev": "imageRedactionCandidateRevision",
        }
    )
    values.update(
        {
            ":expectedStatus": expected_status,
            ":generation": expected_generation,
            ":revision": expected_candidate_revision,
        }
    )
    revision_clause = (
        "(attribute_not_exists(#rev) OR #rev = :revision)"
        if expected_candidate_revision == 0
        else "#rev = :revision"
    )
    scope_clause = append_ticket_access_scope_condition(
        names,
        values,
        expected_municipality_id=expected_municipality_id,
        expected_department_id=expected_department_id,
    )
    return " AND ".join(
        (
            "#rs = :expectedStatus",
            "#rg = :generation",
            revision_clause,
            scope_clause,
        )
    )


def append_content_safety_review_condition(
    names: dict[str, str],
    values: dict[str, Any],
    *,
    expected_status: str,
    expected_generation: int,
    expected_municipality_id: str | None,
    expected_department_id: str | None,
) -> str:
    """Conditional write for a staff content-safety decision against one generation."""
    names.update(
        {
            "#css": "contentSafetyStatus",
            "#csg": "contentSafetyGeneration",
        }
    )
    values.update(
        {
            ":expectedSafetyStatus": expected_status,
            ":safetyGeneration": expected_generation,
        }
    )
    scope_clause = append_ticket_access_scope_condition(
        names,
        values,
        expected_municipality_id=expected_municipality_id,
        expected_department_id=expected_department_id,
    )
    return " AND ".join(
        (
            "#css = :expectedSafetyStatus",
            "#csg = :safetyGeneration",
            scope_clause,
        )
    )


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


def append_expected_values_condition(
    names: dict[str, str],
    values: dict[str, Any],
    expected_values: dict[str, Any],
) -> str:
    """AND-able Dynamo condition for exact current field values (None = absent)."""
    parts: list[str] = []
    for index, (field_name, expected) in enumerate(expected_values.items()):
        alias = f"#exp{index}"
        names[alias] = resolve_ticket_attr_name(field_name)
        if expected is None:
            parts.append(f"attribute_not_exists({alias})")
            continue
        value_key = f":exp{index}"
        values[value_key] = expected
        parts.append(f"{alias} = {value_key}")
    return " AND ".join(parts)


def append_no_pending_unresolved_feedback_condition(
    names: dict[str, str],
    values: dict[str, Any],
) -> str:
    """Reject CLOSED writes while unresolved citizen feedback is still pending review."""
    names["#npufs"] = "resolutionFeedbackStatus"
    names["#npufr"] = "resolutionFeedbackReviewStatus"
    values[":npufUnresolved"] = "STILL_UNRESOLVED"
    values[":npufPending"] = "PENDING"
    return (
        "(attribute_not_exists(#npufs) OR #npufs <> :npufUnresolved "
        "OR attribute_not_exists(#npufr) OR #npufr <> :npufPending)"
    )


def ticket_matches_expected_values(ticket: Any, expected_values: dict[str, Any]) -> bool:
    for field_name, expected in expected_values.items():
        resolve_ticket_attr_name(field_name)
        if getattr(ticket, field_name) != expected:
            return False
    return True


def ticket_has_pending_unresolved_feedback(ticket: Any) -> bool:
    return (
        getattr(ticket, "resolution_feedback_status", None) == "STILL_UNRESOLVED"
        and getattr(ticket, "resolution_feedback_review_status", None) == "PENDING"
    )
