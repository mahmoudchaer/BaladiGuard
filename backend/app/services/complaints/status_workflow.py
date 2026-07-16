from app.schemas.ticket_status import (
    ALLOWED_STATUS_TRANSITIONS,
    STATUS_LABELS,
    TicketStatus,
    is_allowed_status_transition,
    is_known_ticket_status,
)


class InvalidStatusTransitionError(ValueError):
    def __init__(
        self,
        current_status: TicketStatus | str,
        requested_status: TicketStatus | str,
    ) -> None:
        current_label = STATUS_LABELS.get(current_status, str(current_status))  # type: ignore[arg-type]
        requested_label = STATUS_LABELS.get(requested_status, str(requested_status))  # type: ignore[arg-type]
        allowed = sorted(
            ALLOWED_STATUS_TRANSITIONS.get(current_status, frozenset()),  # type: ignore[arg-type]
            key=STATUS_LABELS.get,
        )
        allowed_labels = ", ".join(STATUS_LABELS[status] for status in allowed) or "none"

        if not is_known_ticket_status(str(current_status)) or not is_known_ticket_status(
            str(requested_status)
        ):
            message = (
                f"Invalid ticket status value in transition "
                f"{current_status} -> {requested_status}."
            )
        else:
            message = (
                f"Cannot move ticket from {current_label} to {requested_label}. "
                f"Allowed next statuses: {allowed_labels}."
            )
        super().__init__(message)
        self.current_status = current_status
        self.requested_status = requested_status


def validate_status_transition(
    current_status: TicketStatus | str,
    requested_status: TicketStatus | str,
) -> None:
    if not is_allowed_status_transition(current_status, requested_status):
        raise InvalidStatusTransitionError(current_status, requested_status)
