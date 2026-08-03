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

    preference = user.notification_preferences.ticket_updates
    if preference == "NONE":
        logger.info(
            "Skipping ticket notification because ticket updates are disabled "
            "ticket_id=%s owner_user_id=%s",
            ticket.ticket_id,
            ticket.owner_user_id,
        )
        return None

    if preference == "SMS":
        return NotificationRecipient(phone=user.phone, preferred_channel="SMS")

    if preference == "EMAIL":
        if user.email is None:
            logger.info(
                "Skipping ticket notification because email preference has no email "
                "ticket_id=%s owner_user_id=%s",
                ticket.ticket_id,
                ticket.owner_user_id,
            )
            return None
        return NotificationRecipient(email=str(user.email), preferred_channel="EMAIL")

    if user.email is None:
        return NotificationRecipient(phone=user.phone, preferred_channel="SMS")
    return NotificationRecipient(
        phone=user.phone,
        email=str(user.email),
        preferred_channel="BOTH",
    )
