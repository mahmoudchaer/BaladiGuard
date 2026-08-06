"""Notification services, adapters, and message templates."""

from app.services.notifications.adapters import (
    MockNotificationAdapter,
    NotificationAdapter,
    NotificationDeliveryError,
    NotificationRecipient,
    UnconfiguredRealNotificationAdapter,
    build_notification_adapter,
)
from app.services.notifications.aws_adapter import AwsSesSnsNotificationAdapter
from app.services.notifications.ledger import (
    get_delivery_ledger,
    notification_idempotency_key,
    reset_delivery_ledger,
)
from app.services.notifications.recipients import ticket_notification_recipient
from app.services.notifications.service import emit_ticket_notification
from app.services.notifications.templates import (
    NotificationEvent,
    NotificationMessage,
    render_notification,
    render_ticket_created,
    render_ticket_resolved,
    render_ticket_updated,
    status_text_for,
)

__all__ = [
    "AwsSesSnsNotificationAdapter",
    "MockNotificationAdapter",
    "NotificationAdapter",
    "NotificationDeliveryError",
    "NotificationEvent",
    "NotificationMessage",
    "NotificationRecipient",
    "UnconfiguredRealNotificationAdapter",
    "build_notification_adapter",
    "emit_ticket_notification",
    "get_delivery_ledger",
    "notification_idempotency_key",
    "render_notification",
    "render_ticket_created",
    "render_ticket_resolved",
    "render_ticket_updated",
    "reset_delivery_ledger",
    "status_text_for",
    "ticket_notification_recipient",
]
