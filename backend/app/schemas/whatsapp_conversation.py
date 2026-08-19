"""Persisted WhatsApp conversation row (issue #296)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.services.whatsapp.states import ConversationState

LanguageCode = Literal["en", "ar"]


class WhatsAppConversation(BaseModel):
    """Minimum fields for deterministic guided intake. Never store full webhooks."""

    conversation_key: str = Field(alias="conversationKey")
    business_phone_number_id: str = Field(alias="businessPhoneNumberId")
    sender_wa_id: str = Field(alias="senderWaId")
    canonical_phone: str = Field(alias="canonicalPhone")
    state: ConversationState
    language: LanguageCode = "en"
    version: int = 1
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    address_text: str | None = Field(default=None, alias="addressText")
    location_confirmed: bool = Field(default=False, alias="locationConfirmed")
    pending_address_text: str | None = Field(default=None, alias="pendingAddressText")
    pending_latitude: float | None = Field(default=None, alias="pendingLatitude")
    pending_longitude: float | None = Field(default=None, alias="pendingLongitude")
    media_id: str | None = Field(default=None, alias="mediaId")
    image_object_key: str | None = Field(default=None, alias="imageObjectKey")
    optional_name: str | None = Field(default=None, alias="optionalName")
    skip_optional_name: bool = Field(default=False, alias="skipOptionalName")
    owner_user_id: str | None = Field(default=None, alias="ownerUserId")
    ticket_id: str | None = Field(default=None, alias="ticketId")
    ticket_number: str | None = Field(default=None, alias="ticketNumber")
    tracking_code: str | None = Field(default=None, alias="trackingCode")
    client_submission_key: str | None = Field(default=None, alias="clientSubmissionKey")
    last_inbound_message_id: str | None = Field(default=None, alias="lastInboundMessageId")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    expires_at: str = Field(alias="expiresAt")
    ttl: int | None = None

    model_config = {"populate_by_name": True}

    def collected_snapshot(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "addressText": self.address_text,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "hasPhoto": bool(self.image_object_key),
            "optionalName": self.optional_name,
            "language": self.language,
        }


def conversation_key(*, business_phone_number_id: str, sender_wa_id: str) -> str:
    return f"{business_phone_number_id}#{sender_wa_id}"
