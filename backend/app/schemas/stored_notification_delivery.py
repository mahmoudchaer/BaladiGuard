"""Persisted notification delivery attempt records (issue #183)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DeliveryAttemptStatus = Literal[
    "SUCCEEDED",
    "FAILED_TRANSIENT",
    "FAILED_PERMANENT",
    "SKIPPED_SANDBOX",
    "SKIPPED_INVALID",
    "SKIPPED_THROTTLED",
    "SKIPPED_OPT_OUT",
]

DeliveryChannel = Literal["EMAIL", "SMS"]


class StoredNotificationDelivery(BaseModel):
    """Safe delivery metadata only — no message body, passwords, or full tokens."""

    delivery_id: str = Field(alias="deliveryId")
    idempotency_key: str = Field(alias="idempotencyKey")
    event: str
    ticket_id: str = Field(alias="ticketId")
    status: str
    channel: DeliveryChannel
    attempt_status: DeliveryAttemptStatus = Field(alias="attemptStatus")
    provider_message_id: str | None = Field(default=None, alias="providerMessageId")
    failure_category: str | None = Field(default=None, alias="failureCategory")
    # Redacted destination fingerprint for ops (never full phone/email in clear when avoidable).
    destination_hint: str | None = Field(default=None, alias="destinationHint")
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}
