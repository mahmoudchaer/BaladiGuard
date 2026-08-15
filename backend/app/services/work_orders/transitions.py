"""Work-order state machine and ticket-status path helpers (issue #247)."""

from __future__ import annotations

from collections import deque

from app.schemas.ticket_status import ALLOWED_STATUS_TRANSITIONS, TicketStatus
from app.schemas.work_order import (
    ALLOWED_WORK_ORDER_TRANSITIONS,
    WORK_ORDER_STATE_LABELS,
    WorkOrderState,
    is_active_work_order_state,
    is_allowed_work_order_transition,
)

WORK_ORDER_ELIGIBLE_TICKET_STATUSES: frozenset[TicketStatus] = frozenset(
    {"UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS"}
)


class InvalidWorkOrderTransitionError(ValueError):
    def __init__(
        self,
        current_state: WorkOrderState | str,
        requested_state: WorkOrderState | str,
    ) -> None:
        current_label = WORK_ORDER_STATE_LABELS.get(current_state, str(current_state))  # type: ignore[arg-type]
        requested_label = WORK_ORDER_STATE_LABELS.get(requested_state, str(requested_state))  # type: ignore[arg-type]
        allowed = sorted(ALLOWED_WORK_ORDER_TRANSITIONS.get(current_state, frozenset()))  # type: ignore[arg-type]
        allowed_labels = ", ".join(allowed) or "none"
        super().__init__(
            f"Cannot move work order from {current_label} to {requested_label}. "
            f"Allowed next states: {allowed_labels}."
        )
        self.current_state = current_state
        self.requested_state = requested_state


def validate_work_order_transition(
    current_state: WorkOrderState | str,
    requested_state: WorkOrderState | str,
) -> None:
    if not is_allowed_work_order_transition(current_state, requested_state):
        raise InvalidWorkOrderTransitionError(current_state, requested_state)


def ticket_status_path(
    current: TicketStatus | str, target: TicketStatus | str
) -> list[TicketStatus] | None:
    """Shortest allowed ticket-status path, never skipping documented transitions."""
    if current == target:
        return []
    if current not in ALLOWED_STATUS_TRANSITIONS or target not in ALLOWED_STATUS_TRANSITIONS:
        return None
    queue: deque[tuple[TicketStatus, list[TicketStatus]]] = deque([(current, [])])  # type: ignore[list-item]
    seen: set[str] = {str(current)}
    while queue:
        status, path = queue.popleft()
        for nxt in sorted(ALLOWED_STATUS_TRANSITIONS[status]):  # type: ignore[index]
            if nxt in seen:
                continue
            next_path = [*path, nxt]
            if nxt == target:
                return next_path
            seen.add(nxt)
            queue.append((nxt, next_path))
    return None


def is_work_order_eligible_ticket_status(status: TicketStatus | str) -> bool:
    return status in WORK_ORDER_ELIGIBLE_TICKET_STATUSES


def is_active_state(state: WorkOrderState | str) -> bool:
    return is_active_work_order_state(state)
