"""Notification emit orchestration (issues #39 / #183).

Renders #40 templates, applies idempotency, delivers through a replaceable
adapter, and records safe delivery outcomes. Failures never raise to ticket callers.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.core.metrics import emit_metric
from app.schemas.stored_notification_delivery import StoredNotificationDelivery
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
from app.services.notifications.results import ChannelDeliveryResult, redact_email, redact_phone
from app.services.notifications.templates import NotificationEvent, render_notification

logger = logging.getLogger(__name__)


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _destination_hint(
    channel: str,
    recipient: NotificationRecipient | None,
) -> str | None:
    if recipient is None:
        return None
    if channel == "EMAIL":
        return redact_email(recipient.email)
    if channel in {"SMS", "WHATSAPP"}:
        return redact_phone(recipient.phone)
    return None


def _persist_results(
    *,
    idempotency_key: str,
    event: str,
    ticket_id: str,
    status: str,
    recipient: NotificationRecipient | None,
    results: list[ChannelDeliveryResult],
) -> None:
    if not results:
        return
    try:
        from app.database.store_factory import get_notification_delivery_store

        store = get_notification_delivery_store()
        stamped = _iso_now()
        for result in results:
            store.append(
                StoredNotificationDelivery(
                    deliveryId=f"ndel_{uuid4().hex}",
                    idempotencyKey=idempotency_key,
                    event=str(event),
                    ticketId=ticket_id,
                    status=status,
                    channel=result.channel,
                    attemptStatus=result.status,
                    providerMessageId=result.provider_message_id,
                    failureCategory=result.failure_category,
                    destinationHint=_destination_hint(result.channel, recipient),
                    createdAt=stamped,
                )
            )
    except Exception:
        logger.exception(
            "Notification delivery record write failed ticket_id=%s; primary emit kept.",
            ticket_id,
        )


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

    Returns ``True`` when delivery was attempted successfully (or completed under
    sandbox skip policy after recording), ``False`` when skipped as a duplicate or
    when delivery failed. Never raises.
    """
    key = notification_idempotency_key(event=event, ticket_id=ticket_id, status=status)
    ledger = get_delivery_ledger()
    try:
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
            results = delivery.deliver(message, recipient) or []
            _persist_results(
                idempotency_key=key,
                event=str(event),
                ticket_id=ticket_id,
                status=status,
                recipient=recipient,
                results=results,
            )
            logger.info(
                "Notification delivery completed event=%s ticket_id=%s channels=%s",
                event,
                ticket_id,
                ",".join(f"{item.channel}:{item.status}" for item in results) or "none",
            )
            failed_channels = [item for item in results if item.status.startswith("FAILED")]
            if failed_channels:
                emit_metric(
                    "NotificationFailed",
                    value=float(len(failed_channels)),
                    dimensions={"event": str(event), "outcome": "channel_failed"},
                )
                # Retry only when nothing was delivered. Releasing after a partial
                # success would duplicate channels that already accepted the event.
                if len(failed_channels) == len(results) and any(
                    item.status == "FAILED_TRANSIENT" for item in failed_channels
                ):
                    ledger.release(key)
                    return False
            else:
                emit_metric(
                    "NotificationSucceeded",
                    dimensions={"event": str(event)},
                )
            return True
        except NotificationDeliveryError as exc:
            if exc.channel_results:
                _persist_results(
                    idempotency_key=key,
                    event=str(event),
                    ticket_id=ticket_id,
                    status=status,
                    recipient=recipient,
                    results=exc.channel_results,
                )
            # Transient failures release the claim so a later attempt may succeed
            # without duplicating a completed send. Permanent failures keep the claim
            # to avoid retry storms for invalid recipients / provider rejects.
            if exc.transient:
                ledger.release(key)
            logger.error(
                "Notification delivery failed ticket_id=%s category=%s transient=%s: %s",
                ticket_id,
                exc.category,
                exc.transient,
                exc,
            )
            emit_metric(
                "NotificationFailed",
                dimensions={
                    "event": str(event),
                    "outcome": "delivery_error",
                    "category": exc.category,
                },
            )
            return False
        except Exception:
            ledger.release(key)
            raise
    except Exception as exc:
        logger.error(
            "Notification emit failed for ticket %s (%s).",
            ticket_id,
            type(exc).__name__,
        )
        emit_metric(
            "NotificationFailed",
            dimensions={"event": str(event), "outcome": "emit_error"},
        )
        return False
