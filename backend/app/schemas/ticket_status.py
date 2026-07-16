from typing import Literal

TicketStatus = Literal[
    "SUBMITTED",
    "UNDER_REVIEW",
    "ASSIGNED",
    "IN_PROGRESS",
    "RESOLVED",
    "CLOSED",
]

TICKET_STATUSES: tuple[TicketStatus, ...] = (
    "SUBMITTED",
    "UNDER_REVIEW",
    "ASSIGNED",
    "IN_PROGRESS",
    "RESOLVED",
    "CLOSED",
)

ALLOWED_STATUS_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    "SUBMITTED": frozenset({"UNDER_REVIEW", "CLOSED"}),
    "UNDER_REVIEW": frozenset({"ASSIGNED", "CLOSED"}),
    "ASSIGNED": frozenset({"IN_PROGRESS", "UNDER_REVIEW"}),
    "IN_PROGRESS": frozenset({"RESOLVED", "ASSIGNED"}),
    "RESOLVED": frozenset({"CLOSED", "IN_PROGRESS"}),
    "CLOSED": frozenset(),
}

STATUS_LABELS: dict[TicketStatus, str] = {
    "SUBMITTED": "Submitted",
    "UNDER_REVIEW": "Under Review",
    "ASSIGNED": "Assigned",
    "IN_PROGRESS": "In Progress",
    "RESOLVED": "Resolved",
    "CLOSED": "Closed",
}


def is_known_ticket_status(status: str) -> bool:
    return status in STATUS_LABELS


def is_allowed_status_transition(current: TicketStatus | str, requested: TicketStatus | str) -> bool:
    if not is_known_ticket_status(current) or not is_known_ticket_status(requested):
        return False
    return requested in ALLOWED_STATUS_TRANSITIONS[current]  # type: ignore[index]
