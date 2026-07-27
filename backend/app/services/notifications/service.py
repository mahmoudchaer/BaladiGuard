"""Best-effort notification emit helpers (issue #73 logging + #39-ready hook).

Failures are logged and never raised to callers so ticket create/update stays intact.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def emit_ticket_notification(
    *,
    event: str,
    ticket_id: str,
    status: str,
    tracking_code: str | None = None,
    ticket_number: str | None = None,
) -> None:
    """Log a mock notification for important ticket lifecycle events.

    Real delivery adapters belong to issue #39. This helper exists so notification
    failures are visible in logs during testing/demo without affecting tickets.
    """
    try:
        # Prefer issue #40 templates when available on the branch.
        try:
            from app.services.notifications.templates import render_notification

            message = render_notification(
                event,  # type: ignore[arg-type]
                ticket_id=ticket_id,
                status=status,
                ticket_number=ticket_number,
                tracking_code=tracking_code,
            )
            logger.info(
                "Notification mock delivery event=%s ticket_id=%s status=%s subject=%r",
                message.event,
                message.ticket_id,
                message.status,
                message.subject,
            )
            return
        except ImportError:
            pass
        except Exception as template_exc:
            logger.warning(
                "Notification template render failed for ticket %s (%s); using fallback log.",
                ticket_id,
                type(template_exc).__name__,
            )

        payload: dict[str, Any] = {
            "event": event,
            "ticketId": ticket_id,
            "status": status,
        }
        if tracking_code:
            payload["trackingCode"] = tracking_code
        if ticket_number:
            payload["ticketNumber"] = ticket_number
        logger.info("Notification mock delivery %s", payload)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(
            "Notification emit failed for ticket %s (%s).",
            ticket_id,
            type(exc).__name__,
        )
