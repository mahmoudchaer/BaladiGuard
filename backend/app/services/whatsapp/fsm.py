"""Deterministic WhatsApp conversation state machine (issue #296)."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

from app.config import Settings, get_settings
from app.database.whatsapp_store import ConversationVersionConflict, WhatsAppConversationStore
from app.schemas.location_validation import ValidateLocationRequest
from app.schemas.whatsapp_conversation import WhatsAppConversation, conversation_key
from app.services.location.validate_location import validate_location
from app.services.uploads.photo_upload_service import (
    InvalidUploadError,
    S3UploadError,
    photo_upload_service,
)
from app.services.whatsapp.graph import WhatsAppGraphClient
from app.services.whatsapp.identity import InactiveCitizenError, reconcile_whatsapp_sender
from app.services.whatsapp.prompts import (
    help_text,
    inactive_account_message,
    prompt_for,
    success_receipt,
)
from app.services.whatsapp.states import (
    parse_command,
    previous_editable_state,
)
from app.services.whatsapp.submission import receipt_deep_link, submit_whatsapp_report
from app.services.whatsapp.webhook_parse import InboundWhatsAppEvent

logger = logging.getLogger(__name__)

DEFAULT_TTL_HOURS = 24


class WhatsAppOutboundError(RuntimeError):
    """Graph send failed; webhook must release dedup and remain retryable."""


class WhatsAppFlowEngine:
    def __init__(
        self,
        *,
        conversation_store: WhatsAppConversationStore,
        graph: WhatsAppGraphClient,
        settings: Settings | None = None,
    ) -> None:
        self._store = conversation_store
        self._graph = graph
        self._settings = settings or get_settings()

    def handle_event(self, event: InboundWhatsAppEvent) -> None:
        if event.kind == "status" or event.kind == "ignored":
            return
        if not event.business_phone_number_id or not event.sender_wa_id:
            return

        expected_phone_id = self._settings.whatsapp_phone_number_id
        if expected_phone_id and event.business_phone_number_id != expected_phone_id:
            logger.info("WhatsApp event rejected wrong phone_number_id")
            return

        try:
            reconciled = reconcile_whatsapp_sender(wa_id=event.sender_wa_id)
        except InactiveCitizenError:
            self._safe_send(
                phone_number_id=event.business_phone_number_id,
                to_wa_id=event.sender_wa_id,
                body=inactive_account_message("en"),
            )
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("WhatsApp identity reconcile failed error=%s", type(exc).__name__)
            self._safe_send(
                phone_number_id=event.business_phone_number_id,
                to_wa_id=event.sender_wa_id,
                body=inactive_account_message("en"),
            )
            return

        key = conversation_key(
            business_phone_number_id=event.business_phone_number_id,
            sender_wa_id=event.sender_wa_id,
        )
        conversation = self._store.get(key)
        now = datetime.now(UTC)
        if conversation is None or self._is_expired(conversation, now):
            conversation = self._start_conversation(
                key=key,
                event=event,
                owner_user_id=reconciled.user.user_id,
                canonical_phone=reconciled.user.phone,
                now=now,
            )
            self._reply(conversation, prompt_for(conversation.state, conversation))
            return

        if event.message_id and conversation.last_inbound_message_id == event.message_id:
            self._reply(conversation, prompt_for(conversation.state, conversation))
            return

        expected_version = conversation.version
        conversation.last_inbound_message_id = event.message_id
        command = parse_command(event.text) if event.kind == "text" else None
        try:
            if command == "help":
                self._reply(conversation, help_text(conversation.language))
                return
            if command == "cancel":
                conversation.state = "cancelled"
                conversation = self._persist(conversation, expected_version)
                self._reply(conversation, prompt_for("cancelled", conversation))
                return
            if command == "restart":
                conversation = self._reset_collected(conversation, now=now)
                conversation = self._persist(conversation, expected_version)
                self._reply(conversation, prompt_for(conversation.state, conversation))
                return
            if command == "back":
                previous = previous_editable_state(conversation.state)
                if previous is not None:
                    conversation.state = previous
                    conversation = self._persist(conversation, expected_version)
                self._reply(conversation, prompt_for(conversation.state, conversation))
                return

            conversation = self._advance(conversation, event, expected_version=expected_version)
        except ConversationVersionConflict:
            logger.info("WhatsApp concurrent update ignored conversation")
            return

    def _advance(
        self,
        conversation: WhatsAppConversation,
        event: InboundWhatsAppEvent,
        *,
        expected_version: int,
    ) -> WhatsAppConversation:
        state = conversation.state
        if state in {"completed", "cancelled", "submitting"}:
            self._reply(conversation, prompt_for(state, conversation))
            return conversation

        if state == "welcome":
            text = (event.text or "").strip().casefold()
            if event.kind != "text" or text not in {"yes", "y", "ok", "موافق"}:
                self._reply(conversation, prompt_for(state, conversation))
                return conversation
            conversation.state = "language"
            conversation = self._persist(conversation, expected_version)
            self._reply(conversation, prompt_for(conversation.state, conversation))
            return conversation

        if state == "language":
            text = (event.text or "").strip().casefold()
            if text in {"en", "english"}:
                conversation.language = "en"
            elif text in {"ar", "arabic", "العربية"}:
                conversation.language = "ar"
            else:
                self._reply(conversation, prompt_for(state, conversation))
                return conversation
            conversation.state = "description"
            conversation = self._persist(conversation, expected_version)
            self._reply(conversation, prompt_for(conversation.state, conversation))
            return conversation

        if state == "description":
            if event.kind != "text" or not event.text or len(event.text.strip()) < 10:
                self._reply(
                    conversation,
                    prompt_for(state, conversation)
                    + (
                        "\n(Please send at least 10 characters.)"
                        if conversation.language == "en"
                        else "\n(أرسل 10 أحرف على الأقل.)"
                    ),
                )
                return conversation
            conversation.description = event.text.strip()[:2000]
            conversation.state = "location"
            conversation = self._persist(conversation, expected_version)
            self._reply(conversation, prompt_for(conversation.state, conversation))
            return conversation

        if state == "location":
            return self._handle_location(conversation, event, expected_version=expected_version)

        if state == "photo":
            return self._handle_photo(conversation, event, expected_version=expected_version)

        if state == "optional_name":
            if event.kind != "text" or not event.text:
                self._reply(conversation, prompt_for(state, conversation))
                return conversation
            text = event.text.strip()
            if text.casefold() in {"skip", "no", "تخطي"}:
                conversation.optional_name = None
                conversation.skip_optional_name = True
            else:
                conversation.optional_name = text[:120]
                conversation.skip_optional_name = False
            conversation.state = "review"
            conversation = self._persist(conversation, expected_version)
            self._reply(conversation, prompt_for(conversation.state, conversation))
            return conversation

        if state == "review":
            text = (event.text or "").strip().casefold()
            if text in {"confirm", "yes", "submit", "تأكيد"}:
                return self._submit(conversation, expected_version=expected_version)
            self._reply(conversation, prompt_for(state, conversation))
            return conversation

        self._reply(conversation, prompt_for(state, conversation))
        return conversation

    def _handle_location(
        self,
        conversation: WhatsAppConversation,
        event: InboundWhatsAppEvent,
        *,
        expected_version: int,
    ) -> WhatsAppConversation:
        text = (event.text or "").strip().casefold()
        if (
            conversation.pending_latitude is not None
            and conversation.pending_longitude is not None
            and text in {"yes", "y", "confirm", "تأكيد"}
        ):
            conversation.latitude = conversation.pending_latitude
            conversation.longitude = conversation.pending_longitude
            conversation.address_text = conversation.pending_address_text
            conversation.location_confirmed = True
            conversation.pending_latitude = None
            conversation.pending_longitude = None
            conversation.pending_address_text = None
            conversation.state = "photo"
            conversation = self._persist(conversation, expected_version)
            self._reply(conversation, prompt_for(conversation.state, conversation))
            return conversation

        if event.kind == "location" and event.latitude is not None and event.longitude is not None:
            try:
                validated = validate_location(
                    ValidateLocationRequest(
                        latitude=event.latitude,
                        longitude=event.longitude,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.info("WhatsApp location validate failed error=%s", type(exc).__name__)
                self._reply(
                    conversation,
                    "Could not validate that location. Send another pin or address.",
                )
                return conversation
            if not validated.success or validated.location is None:
                self._reply(
                    conversation,
                    validated.message or "Could not validate that location.",
                )
                return conversation
            conversation.latitude = validated.location.latitude
            conversation.longitude = validated.location.longitude
            conversation.address_text = (
                event.location_address or event.location_name or validated.location.address_text
            )
            conversation.location_confirmed = True
            conversation.state = "photo"
            conversation = self._persist(conversation, expected_version)
            self._reply(conversation, prompt_for(conversation.state, conversation))
            return conversation

        if event.kind == "text" and event.text and len(event.text.strip()) >= 3:
            try:
                validated = validate_location(
                    ValidateLocationRequest(addressText=event.text.strip())
                )
            except Exception:
                self._reply(
                    conversation,
                    "Could not resolve that address. Try again or send a location pin.",
                )
                return conversation
            if not validated.success or validated.location is None:
                self._reply(
                    conversation,
                    validated.message or "Could not resolve that address.",
                )
                return conversation
            conversation.pending_latitude = validated.location.latitude
            conversation.pending_longitude = validated.location.longitude
            conversation.pending_address_text = validated.location.address_text
            conversation = self._persist(conversation, expected_version)
            self._reply(
                conversation,
                f"Resolved location: {conversation.pending_address_text}\n"
                "Reply YES to confirm, or send a different pin/address.",
            )
            return conversation

        self._reply(conversation, prompt_for(conversation.state, conversation))
        return conversation

    def _handle_photo(
        self,
        conversation: WhatsAppConversation,
        event: InboundWhatsAppEvent,
        *,
        expected_version: int,
    ) -> WhatsAppConversation:
        if event.kind != "image" or not event.media_id or not conversation.owner_user_id:
            self._reply(conversation, prompt_for(conversation.state, conversation))
            return conversation
        try:
            body, content_type = self._graph.download_media(media_id=event.media_id)
            object_key = photo_upload_service.upload_report_photo_bytes(
                body,
                owner_user_id=conversation.owner_user_id,
                content_type=content_type if content_type.startswith("image/") else None,
                filename="whatsapp.jpg",
            )
        except (InvalidUploadError, S3UploadError, RuntimeError) as exc:
            logger.info("WhatsApp media ingest failed error=%s", type(exc).__name__)
            self._reply(
                conversation,
                "That photo could not be accepted. Send a JPEG/PNG/WebP under 5MB.",
            )
            return conversation
        conversation.media_id = event.media_id
        conversation.image_object_key = object_key
        conversation.state = "optional_name"
        conversation = self._persist(conversation, expected_version)
        self._reply(conversation, prompt_for(conversation.state, conversation))
        return conversation

    def _submit(
        self,
        conversation: WhatsAppConversation,
        *,
        expected_version: int,
    ) -> WhatsAppConversation:
        conversation.state = "submitting"
        if not conversation.client_submission_key:
            conversation.client_submission_key = (
                f"wa:{conversation.business_phone_number_id}:"
                f"{conversation.sender_wa_id}:{secrets.token_hex(8)}"
            )
        conversation = self._persist(conversation, expected_version)
        expected_version = conversation.version
        self._reply(conversation, prompt_for("submitting", conversation))
        try:
            conversation = submit_whatsapp_report(conversation)
        except Exception as exc:  # noqa: BLE001
            logger.warning("WhatsApp ticket submit failed error=%s", type(exc).__name__)
            conversation.state = "review"
            conversation = self._persist(conversation, expected_version)
            self._reply(
                conversation,
                "Submission failed temporarily. Reply CONFIRM to try again.",
            )
            return conversation
        conversation = self._persist(conversation, expected_version)
        deep_link = receipt_deep_link(conversation.tracking_code)
        self._reply(
            conversation,
            success_receipt(conversation, deep_link=deep_link),
        )
        return conversation

    def _start_conversation(
        self,
        *,
        key: str,
        event: InboundWhatsAppEvent,
        owner_user_id: str,
        canonical_phone: str,
        now: datetime,
    ) -> WhatsAppConversation:
        ttl_hours = self._settings.whatsapp_conversation_ttl_hours
        expires = now + timedelta(hours=ttl_hours)
        conversation = WhatsAppConversation(
            conversationKey=key,
            businessPhoneNumberId=event.business_phone_number_id or "",
            senderWaId=event.sender_wa_id or "",
            canonicalPhone=canonical_phone,
            state="welcome",
            language="en",
            version=1,
            ownerUserId=owner_user_id,
            lastInboundMessageId=event.message_id,
            createdAt=_iso(now),
            updatedAt=_iso(now),
            expiresAt=_iso(expires),
            ttl=int(expires.timestamp()),
        )
        existing = self._store.get(key)
        if existing is not None and not self._is_expired(existing, now):
            return existing
        if existing is not None:
            # Replace expired row via conditional update when possible.
            try:
                return self._store.conditional_update(
                    conversation, expected_version=existing.version
                )
            except ConversationVersionConflict:
                refreshed = self._store.get(key)
                return refreshed or conversation
        try:
            return self._store.put_new(conversation)
        except ConversationVersionConflict:
            refreshed = self._store.get(key)
            return refreshed or conversation

    def _reset_collected(
        self, conversation: WhatsAppConversation, *, now: datetime
    ) -> WhatsAppConversation:
        ttl_hours = self._settings.whatsapp_conversation_ttl_hours
        expires = now + timedelta(hours=ttl_hours)
        conversation.state = "welcome"
        conversation.description = None
        conversation.latitude = None
        conversation.longitude = None
        conversation.address_text = None
        conversation.location_confirmed = False
        conversation.pending_address_text = None
        conversation.pending_latitude = None
        conversation.pending_longitude = None
        conversation.media_id = None
        conversation.image_object_key = None
        conversation.optional_name = None
        conversation.skip_optional_name = False
        conversation.ticket_id = None
        conversation.ticket_number = None
        conversation.tracking_code = None
        conversation.client_submission_key = None
        conversation.updated_at = _iso(now)
        conversation.expires_at = _iso(expires)
        conversation.ttl = int(expires.timestamp())
        return conversation

    def _persist(
        self, conversation: WhatsAppConversation, expected_version: int
    ) -> WhatsAppConversation:
        conversation.updated_at = _iso(datetime.now(UTC))
        return self._store.conditional_update(conversation, expected_version=expected_version)

    def _reply(self, conversation: WhatsAppConversation, body: str) -> None:
        self._safe_send(
            phone_number_id=conversation.business_phone_number_id,
            to_wa_id=conversation.sender_wa_id,
            body=body,
        )

    def _safe_send(self, *, phone_number_id: str, to_wa_id: str, body: str) -> None:
        try:
            self._graph.send_text(
                phone_number_id=phone_number_id,
                to_wa_id=to_wa_id,
                body=body,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("WhatsApp outbound failed error=%s", type(exc).__name__)
            raise WhatsAppOutboundError("WhatsApp outbound send failed.") from exc

    @staticmethod
    def _is_expired(conversation: WhatsAppConversation, now: datetime) -> bool:
        try:
            expires = datetime.fromisoformat(conversation.expires_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        return expires <= now


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
