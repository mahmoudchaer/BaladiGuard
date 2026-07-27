from functools import lru_cache

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings
from app.schemas.stored_status_history import StoredStatusHistory
from app.schemas.stored_ticket import StoredTicket
from app.schemas.ticket_response import (
    CitizenTicketLocation,
    CitizenTicketResponse,
    CitizenTicketTimelineEntry,
    TicketAiFields,
    TicketDepartment,
    TicketDuplicateReference,
    TicketDuplicateSuggestion,
    TicketImageReference,
    TicketResponse,
    TicketStatusHistoryEntry,
)
from app.services.routing import department_name


@lru_cache
def get_s3_client():
    settings = get_settings()
    return boto3.client("s3", region_name=settings.aws_region)


def build_image_url(object_key: str) -> str | None:
    settings = get_settings()
    if not settings.aws_s3_bucket:
        return None

    try:
        return get_s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.aws_s3_bucket, "Key": object_key},
            ExpiresIn=3600,
        )
    except (BotoCoreError, ClientError):
        return None


def build_ticket_ai_fields(ticket: StoredTicket) -> TicketAiFields:
    original_description = ticket.original_description or ticket.description
    return TicketAiFields(
        originalDescription=original_description,
        cleanedDescription=ticket.cleaned_description,
        aiSuggestedCategory=ticket.ai_suggested_category,
        aiCategoryExplanation=ticket.ai_category_explanation,
        aiConfidence=ticket.ai_confidence,
        finalCategory=ticket.final_category,
        categoryReviewedBy=ticket.category_reviewed_by,
        categoryReviewedAt=ticket.category_reviewed_at,
        aiProcessingStatus=ticket.ai_processing_status,
        aiModelVersion=ticket.ai_model_version,
        suggestedCategory=ticket.ai_suggested_category,
        urgencyScore=ticket.urgency_score,
        urgencyReason=ticket.urgency_reason,
    )


def map_ticket_to_citizen_response(
    ticket: StoredTicket,
    status_history: list[StoredStatusHistory] | None = None,
) -> CitizenTicketResponse:
    timeline = [
        CitizenTicketTimelineEntry(
            status=entry.new_status,
            changedAt=entry.created_at,
        )
        for entry in (status_history or [])
    ]
    last_updated_at = ticket.updated_at or ticket.created_at

    return CitizenTicketResponse(
        ticketNumber=ticket.ticket_number,
        trackingCode=ticket.tracking_code,
        status=ticket.status,
        category=ticket.final_category,
        location=CitizenTicketLocation(addressText=ticket.location.address_text),
        createdAt=ticket.created_at,
        updatedAt=ticket.updated_at,
        lastUpdatedAt=last_updated_at,
        timeline=timeline,
    )


def map_ticket_to_response(
    ticket: StoredTicket,
    status_history: list[StoredStatusHistory] | None = None,
    *,
    duplicate_group: TicketDuplicateReference | None = None,
    duplicate_suggestions: list[TicketDuplicateSuggestion] | None = None,
) -> TicketResponse:
    image_reference = TicketImageReference(
        objectKey=ticket.image_object_key,
        url=build_image_url(ticket.image_object_key),
    )
    department = (
        TicketDepartment(
            departmentId=ticket.department_id,
            name=department_name(ticket.department_id) or ticket.department_id,
        )
        if ticket.department_id
        else None
    )

    return TicketResponse(
        ticketId=ticket.ticket_id,
        ticketNumber=ticket.ticket_number,
        trackingCode=ticket.tracking_code,
        description=ticket.description,
        contact=ticket.contact,
        category=ticket.category,
        priority=ticket.priority,
        status=ticket.status,
        location=ticket.location,
        imageReferences=[image_reference],
        imageObjectKey=ticket.image_object_key,
        department=department,
        departmentId=ticket.department_id,
        createdBy=ticket.created_by,
        municipalityId=ticket.municipality_id,
        duplicateGroupId=ticket.duplicate_group_id,
        createdAt=ticket.created_at,
        updatedAt=ticket.updated_at,
        updatedBy=ticket.updated_by,
        ai=build_ticket_ai_fields(ticket),
        statusHistory=[
            TicketStatusHistoryEntry(
                status=entry.new_status,
                changedAt=entry.created_at,
                changedBy=entry.updated_by,
                note=entry.note,
            )
            for entry in (status_history or [])
        ],
        duplicateGroup=duplicate_group,
        duplicateSuggestions=duplicate_suggestions or [],
    )
