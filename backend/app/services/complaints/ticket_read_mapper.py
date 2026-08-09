from functools import lru_cache

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings
from app.database.store_factory import get_citizen_store
from app.schemas.citizen import StoredCitizenUser
from app.schemas.stored_audit_history import StoredAuditHistory
from app.schemas.stored_status_history import StoredStatusHistory
from app.schemas.stored_ticket import StoredTicket
from app.schemas.ticket_response import (
    CitizenTicketDepartment,
    CitizenTicketLocation,
    CitizenTicketResponse,
    CitizenTicketTimelineEntry,
    PublicTicketAttribution,
    PublicTicketMapLocation,
    PublicTicketResponse,
    TicketAiFields,
    TicketAuditHistoryEntry,
    TicketDepartment,
    TicketDuplicateReference,
    TicketDuplicateSuggestion,
    TicketImageReference,
    TicketPublicFields,
    TicketResponse,
    TicketStatusHistoryEntry,
)
from app.services.routing import department_name

CITIZEN_DEPARTMENT_VISIBLE_STATUSES = frozenset({"ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"})


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
            Params={
                "Bucket": settings.aws_s3_bucket,
                "Key": object_key,
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=settings.s3_presigned_url_ttl_seconds,
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
        suggestedDepartmentId=ticket.suggested_department_id,
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
    visible_department = _citizen_visible_department(ticket)

    return CitizenTicketResponse(
        ticketNumber=ticket.ticket_number,
        trackingCode=ticket.tracking_code,
        status=ticket.status,
        category=_citizen_visible_category(ticket),
        location=CitizenTicketLocation(addressText=ticket.location.address_text),
        department=visible_department,
        createdAt=ticket.created_at,
        updatedAt=ticket.updated_at,
        lastUpdatedAt=last_updated_at,
        timeline=timeline,
    )


def _citizen_visible_department(ticket: StoredTicket) -> CitizenTicketDepartment | None:
    if ticket.status not in CITIZEN_DEPARTMENT_VISIBLE_STATUSES or not ticket.department_id:
        return None
    return CitizenTicketDepartment(name=department_name(ticket.department_id) or "Assigned team")


def map_ticket_to_public_response(
    ticket: StoredTicket,
    *,
    owner: StoredCitizenUser | None = None,
) -> PublicTicketResponse:
    public_description = ticket.public_description.strip() if ticket.public_description else ""
    public_location_label = (
        ticket.public_location_label.strip() if ticket.public_location_label else ""
    )
    if not public_description or not public_location_label:
        raise ValueError("Ticket is missing approved public content.")

    # Only staff-approved public photos are projected. Raw upload keys stay private.
    # Presigned URLs may include the approved key in the path; that is expected for
    # time-limited GET access and is not the same as exposing imageObjectKey in JSON.
    approved_photo_key = (ticket.public_image_object_key or "").strip()
    photo_url = build_image_url(approved_photo_key) if approved_photo_key else None

    return PublicTicketResponse(
        ticketNumber=ticket.ticket_number,
        status=ticket.status,
        category=_citizen_visible_category(ticket),
        description=public_description,
        location=CitizenTicketLocation(addressText=public_location_label),
        mapLocation=PublicTicketMapLocation(
            addressText=public_location_label,
            latitude=round(ticket.location.latitude, 3),
            longitude=round(ticket.location.longitude, 3),
        ),
        department=_citizen_visible_department(ticket),
        attribution=_public_attribution(ticket, owner=owner),
        photoUrl=photo_url,
        createdAt=ticket.created_at,
        updatedAt=ticket.updated_at,
    )


def _citizen_visible_category(ticket: StoredTicket) -> str | None:
    return ticket.final_category


def _public_attribution(
    ticket: StoredTicket,
    *,
    owner: StoredCitizenUser | None = None,
) -> PublicTicketAttribution:
    resolved_owner = owner
    if resolved_owner is None and ticket.owner_user_id:
        resolved_owner = get_citizen_store().get(ticket.owner_user_id)
    if (
        resolved_owner is not None
        and resolved_owner.active
        and resolved_owner.public_name_visible
        and resolved_owner.full_name
        and resolved_owner.full_name.strip()
    ):
        return PublicTicketAttribution(displayName=resolved_owner.full_name.strip(), isNamed=True)
    return PublicTicketAttribution(displayName="Community member", isNamed=False)


def map_ticket_to_response(
    ticket: StoredTicket,
    status_history: list[StoredStatusHistory] | None = None,
    *,
    audit_history: list[StoredAuditHistory] | None = None,
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
        ownerUserId=ticket.owner_user_id,
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
        public=TicketPublicFields(
            status=ticket.public_status,
            description=ticket.public_description,
            locationLabel=ticket.public_location_label,
            imageObjectKey=ticket.public_image_object_key,
            publishedAt=ticket.public_published_at,
        ),
        statusHistory=[
            TicketStatusHistoryEntry(
                status=entry.new_status,
                changedAt=entry.created_at,
                changedBy=entry.updated_by,
                note=entry.note,
            )
            for entry in (status_history or [])
        ],
        auditHistory=[
            TicketAuditHistoryEntry(
                actionType=entry.action_type,
                actorId=entry.actor_id,
                actorRole=entry.actor_role,
                summary=entry.summary,
                previousValue=entry.previous_value,
                newValue=entry.new_value,
                changedAt=entry.created_at,
            )
            for entry in (audit_history or [])
        ],
        duplicateGroup=duplicate_group,
        duplicateSuggestions=duplicate_suggestions or [],
    )
