"""Timezone-safe, read-only municipal service-level indicators (issue #250)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.stored_ticket import StoredTicket

SlaState = Literal["on_track", "due_soon", "overdue", "completed", "unavailable"]

# Calendar-hour targets approved for the MVP municipality policy.  Acknowledgement
# is the first staff workflow transition after submission; resolution is terminal.
POLICY_HOURS: dict[str, tuple[int, int]] = {
    "low": (72, 720),
    "medium": (48, 336),
    "high": (24, 168),
    "critical": (4, 48),
}
TERMINAL_STATUSES = frozenset({"RESOLVED", "CLOSED"})


class TicketSla(BaseModel):
    state: SlaState
    acknowledgement_due_at: str | None = Field(default=None, alias="acknowledgementDueAt")
    resolution_due_at: str | None = Field(default=None, alias="resolutionDueAt")
    target_at: str | None = Field(default=None, alias="targetAt")
    remaining_seconds: int | None = Field(default=None, alias="remainingSeconds")
    overdue_seconds: int | None = Field(default=None, alias="overdueSeconds")
    policy_key: str | None = Field(default=None, alias="policyKey")

    model_config = {"populate_by_name": True}


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def derive_ticket_sla(ticket: StoredTicket, *, now: datetime | None = None) -> TicketSla:
    """Return a display-only SLA projection; malformed legacy timestamps are unavailable."""
    created_at = _parse_timestamp(ticket.created_at)
    if created_at is None or ticket.priority not in POLICY_HOURS:
        return TicketSla(state="unavailable")

    acknowledgement_hours, resolution_hours = POLICY_HOURS[ticket.priority]
    acknowledgement_due_at = created_at + timedelta(hours=acknowledgement_hours)
    resolution_due_at = created_at + timedelta(hours=resolution_hours)
    # SUBMITTED has not been acknowledged; every later workflow state has.
    target_at = acknowledgement_due_at if ticket.status == "SUBMITTED" else resolution_due_at
    if ticket.status in TERMINAL_STATUSES:
        return TicketSla(
            state="completed",
            acknowledgementDueAt=_iso(acknowledgement_due_at),
            resolutionDueAt=_iso(resolution_due_at),
            targetAt=_iso(target_at),
            policyKey=ticket.priority,
        )

    comparison_time = (now or datetime.now(UTC)).astimezone(UTC)
    remaining = int((target_at - comparison_time).total_seconds())
    if remaining < 0:
        state: SlaState = "overdue"
    elif remaining <= int(
        (resolution_hours if ticket.status != "SUBMITTED" else acknowledgement_hours) * 3600 * 0.2
    ):
        state = "due_soon"
    else:
        state = "on_track"
    return TicketSla(
        state=state,
        acknowledgementDueAt=_iso(acknowledgement_due_at),
        resolutionDueAt=_iso(resolution_due_at),
        targetAt=_iso(target_at),
        remainingSeconds=max(remaining, 0),
        overdueSeconds=max(-remaining, 0),
        policyKey=ticket.priority,
    )
