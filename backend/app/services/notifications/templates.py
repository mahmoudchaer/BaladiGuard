"""Reusable citizen-facing notification message templates (issue #40 / #257).

These templates are the contract for issue #39 (notification delivery). They do not
send messages themselves — they only render subject/body text from ticket fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.schemas.ticket_status import STATUS_LABELS, TicketStatus, is_known_ticket_status
from app.services.notifications.deep_links import build_ticket_notification_deep_link

NotificationEvent = Literal["ticket_created", "ticket_updated", "ticket_resolved"]

TEMPLATE_VERSION = "v2"

# Terminal outcomes belong on `ticket_resolved`, not `ticket_updated`.
_TERMINAL_STATUSES: frozenset[TicketStatus] = frozenset({"RESOLVED", "CLOSED"})


@dataclass(frozen=True)
class NotificationMessage:
    """Rendered notification payload ready for a delivery adapter."""

    event: NotificationEvent
    subject: str
    body: str
    ticket_id: str
    status: TicketStatus
    status_text: str
    deep_link: str | None = None
    template_version: str = TEMPLATE_VERSION

    def as_dict(self) -> dict[str, str]:
        payload = {
            "event": self.event,
            "subject": self.subject,
            "body": self.body,
            "ticketId": self.ticket_id,
            "status": self.status,
            "statusText": self.status_text,
            "templateVersion": self.template_version,
        }
        if self.deep_link:
            payload["deepLink"] = self.deep_link
        return payload


def status_text_for(status: TicketStatus | str) -> str:
    """Return the short human-readable status label used in templates."""
    if is_known_ticket_status(status):
        return STATUS_LABELS[status]  # type: ignore[index]
    return str(status).replace("_", " ").title()


def _require_known_status(status: TicketStatus | str) -> TicketStatus:
    """Fail closed: unknown statuses never silently default."""
    if not is_known_ticket_status(status):
        raise ValueError(f"Unknown ticket status for notification template: {status!r}")
    return status  # type: ignore[return-value]


def _require_ticket_id(ticket_id: str) -> str:
    normalized_id = ticket_id.strip()
    if not normalized_id:
        raise ValueError("ticket_id is required for notification templates.")
    return normalized_id


def _ticket_reference(*, ticket_id: str, ticket_number: str | None = None) -> str:
    """Citizen-visible reference — never include the raw internal ticket id."""
    _require_ticket_id(ticket_id)
    if ticket_number and ticket_number.strip():
        return ticket_number.strip()
    return "your report"


def _tracking_suffix(tracking_code: str | None) -> str:
    if tracking_code and tracking_code.strip():
        return f" Tracking code: {tracking_code.strip()}."
    return ""


def _deep_link_suffix(tracking_code: str | None) -> tuple[str, str | None]:
    link = build_ticket_notification_deep_link(tracking_code)
    if not link:
        return "", None
    return f" View details: {link}", link


def render_ticket_created(
    *,
    ticket_id: str,
    status: TicketStatus | str = "SUBMITTED",
    ticket_number: str | None = None,
    tracking_code: str | None = None,
) -> NotificationMessage:
    """Template for a newly created ticket."""
    resolved_status = _require_known_status(status)
    label = status_text_for(resolved_status)
    ticket_id_value = _require_ticket_id(ticket_id)
    reference = _ticket_reference(ticket_id=ticket_id_value, ticket_number=ticket_number)
    link_suffix, deep_link = _deep_link_suffix(tracking_code)
    body = (
        f"Your BaladiGuard report {reference} was created. "
        f"Status: {label}.{_tracking_suffix(tracking_code)}{link_suffix}"
    )
    return NotificationMessage(
        event="ticket_created",
        subject=f"BaladiGuard: ticket {reference} created",
        body=body,
        ticket_id=ticket_id_value,
        status=resolved_status,
        status_text=label,
        deep_link=deep_link,
    )


def render_ticket_updated(
    *,
    ticket_id: str,
    status: TicketStatus | str,
    ticket_number: str | None = None,
    tracking_code: str | None = None,
) -> NotificationMessage:
    """Template for an important ticket status update (non-resolved)."""
    resolved_status = _require_known_status(status)
    if resolved_status in _TERMINAL_STATUSES:
        raise ValueError(
            f"Use ticket_resolved for terminal status {resolved_status!r}; "
            "ticket_updated is for non-resolved changes only."
        )
    label = status_text_for(resolved_status)
    ticket_id_value = _require_ticket_id(ticket_id)
    reference = _ticket_reference(ticket_id=ticket_id_value, ticket_number=ticket_number)
    link_suffix, deep_link = _deep_link_suffix(tracking_code)
    body = (
        f"Your BaladiGuard report {reference} was updated. "
        f"Status: {label}.{_tracking_suffix(tracking_code)}{link_suffix}"
    )
    return NotificationMessage(
        event="ticket_updated",
        subject=f"BaladiGuard: ticket {reference} updated",
        body=body,
        ticket_id=ticket_id_value,
        status=resolved_status,
        status_text=label,
        deep_link=deep_link,
    )


def render_ticket_resolved(
    *,
    ticket_id: str,
    status: TicketStatus | str = "RESOLVED",
    ticket_number: str | None = None,
    tracking_code: str | None = None,
) -> NotificationMessage:
    """Template for a resolved or closed ticket outcome."""
    resolved_status = _require_known_status(status)
    if resolved_status not in _TERMINAL_STATUSES:
        raise ValueError(f"ticket_resolved expects RESOLVED or CLOSED, got {resolved_status!r}")
    label = status_text_for(resolved_status)
    ticket_id_value = _require_ticket_id(ticket_id)
    reference = _ticket_reference(ticket_id=ticket_id_value, ticket_number=ticket_number)
    outcome = "resolved" if resolved_status == "RESOLVED" else "closed"
    link_suffix, deep_link = _deep_link_suffix(tracking_code)
    body = (
        f"Your BaladiGuard report {reference} was {outcome}. "
        f"Status: {label}.{_tracking_suffix(tracking_code)}{link_suffix}"
    )
    return NotificationMessage(
        event="ticket_resolved",
        subject=f"BaladiGuard: ticket {reference} {outcome}",
        body=body,
        ticket_id=ticket_id_value,
        status=resolved_status,
        status_text=label,
        deep_link=deep_link,
    )


def render_notification(
    event: NotificationEvent,
    *,
    ticket_id: str,
    status: TicketStatus | str,
    ticket_number: str | None = None,
    tracking_code: str | None = None,
) -> NotificationMessage:
    """Dispatch helper for issue #39 adapters."""
    if event == "ticket_created":
        return render_ticket_created(
            ticket_id=ticket_id,
            status=status,
            ticket_number=ticket_number,
            tracking_code=tracking_code,
        )
    if event == "ticket_resolved":
        return render_ticket_resolved(
            ticket_id=ticket_id,
            status=status,
            ticket_number=ticket_number,
            tracking_code=tracking_code,
        )
    return render_ticket_updated(
        ticket_id=ticket_id,
        status=status,
        ticket_number=ticket_number,
        tracking_code=tracking_code,
    )
