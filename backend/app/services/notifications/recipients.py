"""Notification recipient resolution for ticket lifecycle events."""

from __future__ import annotations

import logging
from typing import Protocol

from app.schemas.citizen import StoredCitizenUser
from app.schemas.stored_ticket import StoredTicket
from app.services.notifications.adapters import NotificationRecipient

logger = logging.getLogger(__name__)


class CitizenLookup(Protocol):
    def get(self, user_id: str) -> StoredCitizenUser | None: ...


def ticket_notification_recipient(
    ticket: StoredTicket,
    *,
    citizen_lookup: CitizenLookup | None = None,
    event: str | None = None,
) -> NotificationRecipient | None:
    """Resolve the current recipient for a ticket notification.

    Account-linked tickets use live citizen notification preferences so opt-out
    and channel changes apply after submission. Legacy unowned tickets keep the
    existing immutable contact snapshot behavior.
    """
    if not ticket.owner_user_id:
        return NotificationRecipient.from_contact(ticket.contact)

    lookup = citizen_lookup
    if lookup is None:
        from app.database.store_factory import get_citizen_store

        lookup = get_citizen_store()

    user = lookup.get(ticket.owner_user_id)
    if user is None or not user.active:
        logger.info(
            "Skipping ticket notification because owner profile is unavailable "
            "ticket_id=%s owner_user_id=%s",
            ticket.ticket_id,
            ticket.owner_user_id,
        )
        return None

    prefs = user.notification_preferences
    event_preference = {
        "ticket_created": prefs.report_created,
        "ticket_updated": prefs.status_changes,
        "ticket_resolved": prefs.resolution_updates,
        "resolution_feedback_received": prefs.resolution_updates,
        "ticket_action_requested": prefs.action_requests,
        "ticket_work_started": prefs.work_updates,
    }.get(event, True)
    if not event_preference:
        logger.info(
            "Skipping ticket notification because event is disabled ticket_id=%s event=%s",
            ticket.ticket_id,
            event,
        )
        return None
    channels: list[str] = []
    if prefs.email_enabled and user.email is not None:
        channels.append("EMAIL")
    if prefs.whatsapp_enabled:
        channels.append("WHATSAPP")
    push_tokens = tuple(device.token for device in user.push_devices if device.active)
    if prefs.push_enabled and push_tokens:
        channels.append("PUSH")

    # Backward-compatible migration for records written before issue #317.
    preference = prefs.ticket_updates
    explicit_channels = prefs.preference_version >= 2
    if not explicit_channels:
        # Exact legacy projection for older clients/tests. New preference writes never
        # choose ordinary SMS, but existing stored SMS selections remain reversible.
        if preference == "SMS":
            return NotificationRecipient(phone=user.phone, preferred_channel="SMS")
        if preference == "EMAIL" and user.email is not None:
            return NotificationRecipient(email=str(user.email), preferred_channel="EMAIL")
        if preference == "BOTH":
            return NotificationRecipient(
                phone=user.phone,
                email=str(user.email) if user.email else None,
                preferred_channel="BOTH" if user.email else "SMS",
            )

    if not channels:
        logger.info(
            "Skipping ticket notification because ticket updates are disabled "
            "ticket_id=%s owner_user_id=%s",
            ticket.ticket_id,
            ticket.owner_user_id,
        )
        return None

    return NotificationRecipient(
        phone=user.phone,
        email=str(user.email) if "EMAIL" in channels and user.email else None,
        preferred_channel=channels[0] if len(channels) == 1 else "MULTI",
        channels=tuple(channels),
        push_tokens=push_tokens,
    )
