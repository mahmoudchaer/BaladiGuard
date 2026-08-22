"""Shared WhatsApp → ticket submission path (issue #296)."""

from __future__ import annotations

import logging

from app.core.rate_limit import check_identity_rate_limit
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


class WhatsAppSubmissionRateLimited(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("WhatsApp submission rate limited.")
        self.retry_after_seconds = retry_after_seconds


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

    if not _has_reusable_whatsapp_submission(conversation):
        decision = check_identity_rate_limit(
            f"wa:{conversation.canonical_phone}",
            "whatsapp-submission",
        )
        if not decision.allowed:
            raise WhatsAppSubmissionRateLimited(decision.retry_after_seconds)

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


def _has_reusable_whatsapp_submission(conversation: WhatsAppConversation) -> bool:
    """True when this CONFIRM retry can replay an already-created ticket."""
    from app.services.complaints.ticket_submission_idempotency import (
        composite_submission_key,
        get_ticket_submission_idempotency_store,
        normalize_client_submission_key,
    )

    client_key = normalize_client_submission_key(conversation.client_submission_key)
    owner_user_id = conversation.owner_user_id
    if not client_key or not owner_user_id:
        return False
    store = get_ticket_submission_idempotency_store()
    composite = composite_submission_key(owner_user_id=owner_user_id, client_key=client_key)
    if store.get_completed(composite) is not None:
        return True
    if store.try_recover(composite) is not None:
        return True
    pending = store.get_pending_ticket_id(composite)
    return bool(pending)


def receipt_deep_link(tracking_code: str | None) -> str | None:
    if not tracking_code:
        return None
    return build_ticket_notification_deep_link(tracking_code)
