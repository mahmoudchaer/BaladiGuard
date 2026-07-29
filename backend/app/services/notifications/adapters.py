"""Replaceable notification delivery adapters (issue #39).

Templates (#40) render message text. Adapters deliver that text. The MVP ships a
mock adapter that logs clearly marked mock output. A real SMS/email provider can
replace the mock without changing ticket create/status callers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Protocol

from app.schemas.ticket import ReportContact
from app.services.notifications.templates import NotificationMessage

logger = logging.getLogger(__name__)

DeliveryMode = Literal["mock", "real"]


@dataclass(frozen=True, slots=True)
class NotificationRecipient:
    """Citizen recipient context when contact details are available on the ticket."""

    name: str | None = None
    phone: str | None = None
    email: str | None = None
    preferred_channel: str | None = None

    @classmethod
    def from_contact(cls, contact: ReportContact | None) -> NotificationRecipient | None:
        if contact is None:
            return None
        if not contact.phone and not contact.email:
            return None
        return cls(
            name=contact.name,
            phone=contact.phone,
            email=str(contact.email) if contact.email else None,
            preferred_channel=contact.preferred_channel,
        )


class NotificationDeliveryError(RuntimeError):
    """Raised when a delivery adapter fails. Callers must not roll back tickets."""


class NotificationAdapter(Protocol):
    """Small delivery contract for issue #39."""

    @property
    def mode(self) -> DeliveryMode:
        """``mock`` for demo/logging; ``real`` for actual provider delivery."""

    def deliver(
        self,
        message: NotificationMessage,
        recipient: NotificationRecipient | None = None,
    ) -> None:
        """Deliver one rendered notification. May raise ``NotificationDeliveryError``."""


class MockNotificationAdapter:
    """MVP adapter that logs mock delivery output (not actual SMS/email)."""

    @property
    def mode(self) -> DeliveryMode:
        return "mock"

    def deliver(
        self,
        message: NotificationMessage,
        recipient: NotificationRecipient | None = None,
    ) -> None:
        logger.info(
            "Notification mock delivery mode=mock event=%s ticket_id=%s status=%s "
            "tracking_context=%s recipient_phone=%s recipient_email=%s "
            "preferred_channel=%s subject=%r",
            message.event,
            message.ticket_id,
            message.status,
            "present" if "Tracking code:" in message.body else "absent",
            recipient.phone if recipient else None,
            recipient.email if recipient else None,
            recipient.preferred_channel if recipient else None,
            message.subject,
        )


class UnconfiguredRealNotificationAdapter:
    """Placeholder real adapter until SNS/SES (or similar) is wired.

    Selecting ``NOTIFICATION_ADAPTER=real`` without a provider must not silently
    look like successful mock delivery — it fails closed with a clear error.
    """

    @property
    def mode(self) -> DeliveryMode:
        return "real"

    def deliver(
        self,
        message: NotificationMessage,
        recipient: NotificationRecipient | None = None,
    ) -> None:
        raise NotificationDeliveryError(
            "Real notification delivery is not configured for this environment "
            f"(event={message.event}, ticket_id={message.ticket_id})."
        )


def build_notification_adapter(mode: str | None = None) -> NotificationAdapter:
    """Factory used by the notification service (config-driven)."""
    from app.config import get_settings

    selected = (mode or get_settings().notification_adapter).strip().lower()
    if selected == "real":
        return UnconfiguredRealNotificationAdapter()
    return MockNotificationAdapter()
