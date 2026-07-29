"""Notification emit orchestration (issue #39).

Renders #40 templates, applies idempotency, and delivers through a replaceable
adapter. Failures are logged and never raised to ticket create/status callers.
"""

from __future__ import annotations

import logging

from app.services.notifications.adapters import (
    NotificationAdapter,
    NotificationDeliveryError,
    NotificationRecipient,
    build_notification_adapter,
)
from app.services.notifications.ledger import (
    get_delivery_ledger,
    notification_idempotency_key,
)
from app.services.notifications.templates import NotificationEvent, render_notification

logger = logging.getLogger(__name__)


def emit_ticket_notification(
    *,
    event: NotificationEvent | str,
    ticket_id: str,
    status: str,
    tracking_code: str | None = None,
    ticket_number: str | None = None,
    recipient: NotificationRecipient | None = None,
    adapter: NotificationAdapter | None = None,
) -> bool:
    """Emit one lifecycle notification.

    Returns ``True`` when delivery was attempted (and succeeded), ``False`` when
    skipped as a duplicate or when delivery failed. Never raises.
    """
    try:
        key = notification_idempotency_key(event=event, ticket_id=ticket_id, status=status)
        ledger = get_delivery_ledger()
        if not ledger.claim(key):
            logger.info(
                "Notification skipped duplicate event=%s ticket_id=%s status=%s",
                event,
                ticket_id,
                status,
            )
            return False

        try:
            message = render_notification(
                event,  # type: ignore[arg-type]
                ticket_id=ticket_id,
                status=status,
                ticket_number=ticket_number,
                tracking_code=tracking_code,
            )
            delivery = adapter or build_notification_adapter()
            delivery.deliver(message, recipient)
            return True
        except Exception:
            # Failed attempts must not permanently suppress retries.
            ledger.release(key)
            raise
    except NotificationDeliveryError as exc:
        logger.error(
            "Notification delivery failed for ticket %s (%s): %s",
            ticket_id,
            type(exc).__name__,
            exc,
        )
        return False
    except Exception as exc:
        logger.error(
            "Notification emit failed for ticket %s (%s).",
            ticket_id,
            type(exc).__name__,
        )
        return False
