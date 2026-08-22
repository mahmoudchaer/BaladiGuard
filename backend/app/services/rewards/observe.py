"""Fail-safe ticket hooks for the contribution ledger (issue #323)."""

from __future__ import annotations

import logging

from app.schemas.stored_ticket import StoredTicket

logger = logging.getLogger(__name__)


def observe_ticket_rewards(ticket: StoredTicket | None) -> None:
    """Sync rewards for a persisted ticket. Never raises into the ticket path."""
    if ticket is None:
        return
    try:
        from app.services.rewards.service import rewards_service

        rewards_service.sync_ticket(ticket)
    except Exception:
        logger.exception("Rewards sync failed ticket=%s", getattr(ticket, "ticket_id", None))
