"""Unit tests for ticket status workflow validation."""

from __future__ import annotations

import pytest

from app.schemas.ticket_status import (
    ALLOWED_STATUS_TRANSITIONS,
    TICKET_STATUSES,
    TicketStatus,
    is_allowed_status_transition,
)
from app.services.complaints.status_workflow import (
    InvalidStatusTransitionError,
    validate_status_transition,
)


def _all_allowed_edges() -> list[tuple[TicketStatus, TicketStatus]]:
    edges: list[tuple[TicketStatus, TicketStatus]] = []
    for current, allowed in ALLOWED_STATUS_TRANSITIONS.items():
        for requested in sorted(allowed):
            edges.append((current, requested))
    return edges


def _illegal_transitions() -> list[tuple[TicketStatus, TicketStatus]]:
    illegal: list[tuple[TicketStatus, TicketStatus]] = []
    for current in TICKET_STATUSES:
        allowed = ALLOWED_STATUS_TRANSITIONS[current]
        for requested in TICKET_STATUSES:
            if requested not in allowed:
                illegal.append((current, requested))
    return illegal


@pytest.mark.parametrize(("current", "requested"), _all_allowed_edges())
def test_validate_status_transition_allows_documented_edges(
    current: TicketStatus,
    requested: TicketStatus,
) -> None:
    validate_status_transition(current, requested)
    assert is_allowed_status_transition(current, requested), (
        f"status_workflow: expected allowed transition {current} -> {requested}"
    )


@pytest.mark.parametrize(("current", "requested"), _illegal_transitions())
def test_validate_status_transition_rejects_illegal_edges(
    current: TicketStatus,
    requested: TicketStatus,
) -> None:
    with pytest.raises(InvalidStatusTransitionError) as exc_info:
        validate_status_transition(current, requested)

    error = exc_info.value
    assert error.current_status == current
    assert error.requested_status == requested
    assert "Cannot move ticket from" in str(error), (
        f"status_workflow: expected clear message for {current} -> {requested}, got {error!s}"
    )
    assert not is_allowed_status_transition(current, requested), (
        f"status_workflow: expected illegal transition {current} -> {requested}"
    )


def test_closed_has_no_allowed_next_statuses() -> None:
    assert ALLOWED_STATUS_TRANSITIONS["CLOSED"] == frozenset(), (
        "status_workflow: CLOSED must be terminal"
    )


def test_invalid_transition_message_lists_allowed_next_statuses() -> None:
    with pytest.raises(InvalidStatusTransitionError) as exc_info:
        validate_status_transition("SUBMITTED", "RESOLVED")

    message = str(exc_info.value)
    assert "Submitted" in message
    assert "Resolved" in message
    assert "Under Review" in message
    assert "Closed" in message
