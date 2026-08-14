"""Replaceable notification delivery adapters (issues #39 / #183).

Templates (#40) render message text. Adapters deliver that text. Local demos use
the mock adapter. Production uses SES email and SNS SMS when configured.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Protocol

from app.schemas.ticket import ReportContact
from app.services.notifications.results import (
    ChannelDeliveryResult,
    redact_email,
    redact_phone,
)
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

    def __init__(
        self,
        message: str,
        *,
        category: str = "unknown",
        transient: bool = False,
        channel_results: list[ChannelDeliveryResult] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.transient = transient
        self.channel_results = channel_results or []


class NotificationAdapter(Protocol):
    """Small delivery contract for issues #39 / #183."""

    @property
    def mode(self) -> DeliveryMode:
        """``mock`` for demo/logging; ``real`` for actual provider delivery."""

    def deliver(
        self,
        message: NotificationMessage,
        recipient: NotificationRecipient | None = None,
    ) -> list[ChannelDeliveryResult]:
        """Deliver one rendered notification.

        Returns per-channel results on success. May raise ``NotificationDeliveryError``.
        """


class MockNotificationAdapter:
    """MVP adapter that logs mock delivery output (not actual SMS/email)."""

    @property
    def mode(self) -> DeliveryMode:
        return "mock"

    def deliver(
        self,
        message: NotificationMessage,
        recipient: NotificationRecipient | None = None,
    ) -> list[ChannelDeliveryResult]:
        logger.info(
            "Notification mock delivery mode=mock event=%s ticket_id=%s status=%s "
            "tracking_context=%s recipient_phone=%s recipient_email=%s "
            "preferred_channel=%s subject=%r",
            message.event,
            message.ticket_id,
            message.status,
            "present" if "Tracking code:" in message.body else "absent",
            redact_phone(recipient.phone) if recipient else None,
            redact_email(recipient.email) if recipient else None,
            recipient.preferred_channel if recipient else None,
            message.subject,
        )
        results: list[ChannelDeliveryResult] = []
        preference = (recipient.preferred_channel if recipient else None) or ""
        preference = preference.upper()
        if preference == "EMAIL" and recipient and recipient.email:
            results.append(
                ChannelDeliveryResult(
                    channel="EMAIL",
                    status="SUCCEEDED",
                    provider_message_id="mock-email",
                )
            )
        elif preference == "SMS" and recipient and recipient.phone:
            results.append(
                ChannelDeliveryResult(
                    channel="SMS",
                    status="SUCCEEDED",
                    provider_message_id="mock-sms",
                )
            )
        elif preference == "BOTH" and recipient:
            if recipient.phone:
                results.append(
                    ChannelDeliveryResult(
                        channel="SMS",
                        status="SUCCEEDED",
                        provider_message_id="mock-sms",
                    )
                )
            if recipient.email:
                results.append(
                    ChannelDeliveryResult(
                        channel="EMAIL",
                        status="SUCCEEDED",
                        provider_message_id="mock-email",
                    )
                )
        elif recipient and recipient.phone:
            results.append(
                ChannelDeliveryResult(
                    channel="SMS",
                    status="SUCCEEDED",
                    provider_message_id="mock-sms",
                )
            )
        elif recipient and recipient.email:
            results.append(
                ChannelDeliveryResult(
                    channel="EMAIL",
                    status="SUCCEEDED",
                    provider_message_id="mock-email",
                )
            )
        else:
            results.append(
                ChannelDeliveryResult(
                    channel="SMS",
                    status="SUCCEEDED",
                    provider_message_id="mock",
                )
            )
        return results


class UnconfiguredRealNotificationAdapter:
    """Fails closed when real mode is selected but AWS delivery is not configured."""

    @property
    def mode(self) -> DeliveryMode:
        return "real"

    def deliver(
        self,
        message: NotificationMessage,
        recipient: NotificationRecipient | None = None,
    ) -> list[ChannelDeliveryResult]:
        raise NotificationDeliveryError(
            "Real notification delivery is not configured for this environment "
            f"(event={message.event}, ticket_id={message.ticket_id}). "
            "Set SES_FROM_EMAIL (and AWS credentials/region) for email, and ensure "
            "SNS SMS is enabled for phone delivery.",
            category="not_configured",
            transient=False,
        )


def build_notification_adapter(mode: str | None = None) -> NotificationAdapter:
    """Factory used by the notification service (config-driven)."""
    from app.config import get_settings

    settings = get_settings()
    selected = (mode or settings.notification_adapter).strip().lower()
    if selected == "real":
        # Email is the primary “at least one channel” path: require verified SES identity.
        # SNS SMS works without SES_FROM when preference is SMS-only.
        if settings.ses_from_email or settings.notification_allow_sms_only_real:
            from app.services.notifications.aws_adapter import AwsSesSnsNotificationAdapter

            return AwsSesSnsNotificationAdapter(settings=settings)
        return UnconfiguredRealNotificationAdapter()
    return MockNotificationAdapter()
