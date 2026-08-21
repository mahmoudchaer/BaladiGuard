"""Shared WhatsApp → ticket submission path (issue #296)."""

from __future__ import annotations

import logging

from app.schemas.ticket import (
    ClientMetadata,
    ReportContact,
    ReportLocation,
    SubmitTicketRequest,
)
from app.schemas.whatsapp_conversation import WhatsAppConversation
from app.services.ai_job_queue import ai_job_queue
from app.services.complaints.ticket_service import ticket_service
from app.services.content_safety.queue import content_safety_queue
from app.services.notifications.deep_links import build_ticket_notification_deep_link
from app.services.redaction.queue import image_redaction_queue

logger = logging.getLogger(__name__)


def submit_whatsapp_report(conversation: WhatsAppConversation) -> WhatsAppConversation:
    """Create one ticket via TicketService and enqueue the same downstream work as HTTP."""
    if not conversation.owner_user_id:
        raise RuntimeError("WhatsApp submission requires a reconciled owner.")
    if (
        not conversation.description
        or conversation.latitude is None
        or conversation.longitude is None
        or not conversation.address_text
        or not conversation.image_object_key
    ):
        raise RuntimeError("WhatsApp conversation is incomplete for submission.")

    contact = ReportContact(
        name=conversation.optional_name,
        phone=conversation.canonical_phone,
        preferredChannel="SMS",
    )
    payload = SubmitTicketRequest(
        description=conversation.description,
        languageHint=conversation.language,
        location=ReportLocation(
            latitude=conversation.latitude,
            longitude=conversation.longitude,
            addressText=conversation.address_text,
            source="GPS",
        ),
        imageObjectKey=conversation.image_object_key,
        clientMetadata=ClientMetadata(platform="whatsapp", appVersion="cloud-api"),
        clientSubmissionId=conversation.client_submission_key,
    )

    response = ticket_service.submit_ticket(
        payload,
        owner_user_id=conversation.owner_user_id,
        contact=contact,
        client_submission_key=conversation.client_submission_key,
    )

    try:
        ai_job_queue.enqueue(response.ticket_id)
    except Exception as exc:  # noqa: BLE001 - mirror HTTP route resilience
        logger.warning(
            "WhatsApp AI queue write deferred error=%s",
            type(exc).__name__,
        )
    try:
        image_redaction_queue.enqueue(response.ticket_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "WhatsApp image redaction queue write deferred error=%s",
            type(exc).__name__,
        )
    try:
        content_safety_queue.enqueue(response.ticket_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "WhatsApp content safety queue write deferred error=%s",
            type(exc).__name__,
        )

    conversation.ticket_id = response.ticket_id
    conversation.ticket_number = response.ticket_number
    conversation.tracking_code = response.tracking_code
    conversation.state = "completed"
    return conversation


def receipt_deep_link(tracking_code: str | None) -> str | None:
    if not tracking_code:
        return None
    return build_ticket_notification_deep_link(tracking_code)
