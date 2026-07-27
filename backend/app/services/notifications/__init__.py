"""Notification services and message templates."""

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
    "NotificationEvent",
    "NotificationMessage",
    "emit_ticket_notification",
    "render_notification",
    "render_ticket_created",
    "render_ticket_resolved",
    "render_ticket_updated",
    "status_text_for",
]
