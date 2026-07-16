from functools import lru_cache

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings
from app.schemas.stored_status_history import StoredStatusHistory
from app.schemas.stored_ticket import StoredTicket
from app.schemas.ticket_response import (
    TicketAiFields,
    TicketDepartment,
    TicketImageReference,
    TicketResponse,
    TicketStatusHistoryEntry,
)

DEPARTMENT_NAMES: dict[str, str] = {
    "d1111111-1111-1111-1111-111111111111": "Road Maintenance",
    "d2222222-2222-2222-2222-222222222222": "Waste Management",
    "d3333333-3333-3333-3333-333333333333": "Street Lighting",
    "d4444444-4444-4444-4444-444444444444": "Water Services",
    "d5555555-5555-5555-5555-555555555555": "Noise Control",
    "d6666666-6666-6666-6666-666666666666": "Traffic Management",
    "d7777777-7777-7777-7777-777777777777": "Drainage",
    "d8888888-8888-8888-8888-888888888888": "Public Facilities",
}


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
    )


def map_ticket_to_response(
    ticket: StoredTicket,
    status_history: list[StoredStatusHistory] | None = None,
) -> TicketResponse:
    image_reference = TicketImageReference(
        objectKey=ticket.image_object_key,
        url=build_image_url(ticket.image_object_key),
    )
    department = (
        TicketDepartment(
            departmentId=ticket.department_id,
            name=DEPARTMENT_NAMES.get(ticket.department_id, ticket.department_id),
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
    )
