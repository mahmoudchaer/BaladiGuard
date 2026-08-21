"""Parse Meta WhatsApp Cloud API webhook payloads into inbound events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

InboundKind = Literal["text", "location", "image", "unsupported", "status", "ignored"]


@dataclass(frozen=True)
class InboundWhatsAppEvent:
    kind: InboundKind
    message_id: str | None
    business_phone_number_id: str | None
    sender_wa_id: str | None
    text: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_name: str | None = None
    location_address: str | None = None
    media_id: str | None = None
    mime_type: str | None = None


def parse_webhook_payload(payload: dict[str, Any]) -> list[InboundWhatsAppEvent]:
    """Extract citizen message events; status/read receipts become ignored status events."""
    if payload.get("object") != "whatsapp_business_account":
        return []

    events: list[InboundWhatsAppEvent] = []
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
            phone_number_id = metadata.get("phone_number_id")
            business_id = str(phone_number_id) if phone_number_id else None

            for status in value.get("statuses") or []:
                if not isinstance(status, dict):
                    continue
                events.append(
                    InboundWhatsAppEvent(
                        kind="status",
                        message_id=str(status.get("id")) if status.get("id") else None,
                        business_phone_number_id=business_id,
                        sender_wa_id=None,
                    )
                )

            for message in value.get("messages") or []:
                if not isinstance(message, dict):
                    continue
                msg_id = str(message.get("id")) if message.get("id") else None
                sender = str(message.get("from")) if message.get("from") else None
                msg_type = str(message.get("type") or "").strip().lower()
                if msg_type == "text":
                    text_obj = message.get("text") if isinstance(message.get("text"), dict) else {}
                    body = text_obj.get("body")
                    events.append(
                        InboundWhatsAppEvent(
                            kind="text",
                            message_id=msg_id,
                            business_phone_number_id=business_id,
                            sender_wa_id=sender,
                            text=str(body) if body is not None else None,
                        )
                    )
                elif msg_type == "location":
                    loc = (
                        message.get("location") if isinstance(message.get("location"), dict) else {}
                    )
                    events.append(
                        InboundWhatsAppEvent(
                            kind="location",
                            message_id=msg_id,
                            business_phone_number_id=business_id,
                            sender_wa_id=sender,
                            latitude=_finite_float(loc.get("latitude")),
                            longitude=_finite_float(loc.get("longitude")),
                            location_name=str(loc["name"]) if loc.get("name") else None,
                            location_address=(str(loc["address"]) if loc.get("address") else None),
                        )
                    )
                elif msg_type == "image":
                    image = message.get("image") if isinstance(message.get("image"), dict) else {}
                    events.append(
                        InboundWhatsAppEvent(
                            kind="image",
                            message_id=msg_id,
                            business_phone_number_id=business_id,
                            sender_wa_id=sender,
                            media_id=str(image["id"]) if image.get("id") else None,
                            mime_type=str(image["mime_type"]) if image.get("mime_type") else None,
                        )
                    )
                else:
                    events.append(
                        InboundWhatsAppEvent(
                            kind="unsupported",
                            message_id=msg_id,
                            business_phone_number_id=business_id,
                            sender_wa_id=sender,
                        )
                    )
    return events


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number
