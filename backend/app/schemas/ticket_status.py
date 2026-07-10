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


def is_allowed_status_transition(current: TicketStatus, requested: TicketStatus) -> bool:
    return requested in ALLOWED_STATUS_TRANSITIONS[current]
