from app.schemas.ticket_status import (
    ALLOWED_STATUS_TRANSITIONS,
    STATUS_LABELS,
    TicketStatus,
    is_allowed_status_transition,
)


class InvalidStatusTransitionError(ValueError):
    def __init__(self, current_status: TicketStatus, requested_status: TicketStatus) -> None:
        current_label = STATUS_LABELS[current_status]
        requested_label = STATUS_LABELS[requested_status]
        allowed = sorted(ALLOWED_STATUS_TRANSITIONS[current_status], key=STATUS_LABELS.get)
        allowed_labels = ", ".join(STATUS_LABELS[status] for status in allowed) or "none"
        message = (
            f"Cannot move ticket from {current_label} to {requested_label}. "
            f"Allowed next statuses: {allowed_labels}."
        )
        super().__init__(message)
        self.current_status = current_status
        self.requested_status = requested_status


def validate_status_transition(
    current_status: TicketStatus,
    requested_status: TicketStatus,
) -> None:
    if not is_allowed_status_transition(current_status, requested_status):
        raise InvalidStatusTransitionError(current_status, requested_status)
