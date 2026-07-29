"""Ticket list query filters for staff dashboard reads (issue #142)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from app.schemas.stored_ticket import ReportPriority, StoredTicket
from app.schemas.ticket_status import TICKET_STATUSES, TicketStatus, is_known_ticket_status
from app.services.ai.categories import allowed_category_ids
from app.services.routing import department_ids

URGENCY_LEVELS: tuple[ReportPriority, ...] = ("low", "medium", "high", "critical")


@dataclass(frozen=True, slots=True)
class TicketListFilters:
    """Optional AND-combined filters over persisted ticket fields."""

    status: TicketStatus | None = None
    category: str | None = None
    urgency: ReportPriority | None = None
    department_id: str | None = None


@dataclass(frozen=True, slots=True)
class TicketListFilterValidationError:
    field: str
    message: str


def parse_ticket_list_filters(
    *,
    status: str | None = None,
    category: str | None = None,
    urgency: str | None = None,
    department_id: str | None = None,
) -> tuple[TicketListFilters | None, list[TicketListFilterValidationError]]:
    """Validate raw query values and build filters.

    Omitted / null values mean \"no filter\". Blank strings are rejected so callers
    cannot accidentally treat whitespace as a match key.
    """

    errors: list[TicketListFilterValidationError] = []
    parsed_status: TicketStatus | None = None
    parsed_category: str | None = None
    parsed_urgency: ReportPriority | None = None
    parsed_department_id: str | None = None

    if status is not None:
        normalized_status = status.strip()
        if not normalized_status:
            errors.append(
                TicketListFilterValidationError(
                    field="status",
                    message="Status filter must not be empty.",
                )
            )
        elif not is_known_ticket_status(normalized_status):
            supported = ", ".join(TICKET_STATUSES)
            errors.append(
                TicketListFilterValidationError(
                    field="status",
                    message=f"Status must be one of: {supported}.",
                )
            )
        else:
            parsed_status = cast(TicketStatus, normalized_status)

    if category is not None:
        normalized_category = category.strip()
        if not normalized_category:
            errors.append(
                TicketListFilterValidationError(
                    field="category",
                    message="Category filter must not be empty.",
                )
            )
        elif normalized_category not in allowed_category_ids():
            supported = ", ".join(sorted(allowed_category_ids()))
            errors.append(
                TicketListFilterValidationError(
                    field="category",
                    message=f"Category must be one of: {supported}.",
                )
            )
        else:
            parsed_category = normalized_category

    if urgency is not None:
        normalized_urgency = urgency.strip().lower()
        if not normalized_urgency:
            errors.append(
                TicketListFilterValidationError(
                    field="urgency",
                    message="Urgency filter must not be empty.",
                )
            )
        elif normalized_urgency not in URGENCY_LEVELS:
            supported = ", ".join(URGENCY_LEVELS)
            errors.append(
                TicketListFilterValidationError(
                    field="urgency",
                    message=f"Urgency must be one of: {supported}.",
                )
            )
        else:
            parsed_urgency = cast(ReportPriority, normalized_urgency)

    if department_id is not None:
        normalized_department_id = department_id.strip()
        if not normalized_department_id:
            errors.append(
                TicketListFilterValidationError(
                    field="departmentId",
                    message="Department filter must not be empty.",
                )
            )
        elif normalized_department_id not in department_ids():
            supported = ", ".join(sorted(department_ids()))
            errors.append(
                TicketListFilterValidationError(
                    field="departmentId",
                    message=f"Department must be one of: {supported}.",
                )
            )
        else:
            parsed_department_id = normalized_department_id

    if errors:
        return None, errors

    return (
        TicketListFilters(
            status=parsed_status,
            category=parsed_category,
            urgency=parsed_urgency,
            department_id=parsed_department_id,
        ),
        [],
    )


def ticket_matches_filters(ticket: StoredTicket, filters: TicketListFilters) -> bool:
    """Return True when a ticket matches every provided persisted-field filter."""

    if filters.status is not None and ticket.status != filters.status:
        return False
    if filters.category is not None and ticket.category != filters.category:
        return False
    if filters.urgency is not None and ticket.priority != filters.urgency:
        return False
    if filters.department_id is not None and ticket.department_id != filters.department_id:
        return False
    return True


def filter_stored_tickets(
    tickets: list[StoredTicket],
    filters: TicketListFilters | None,
) -> list[StoredTicket]:
    if filters is None:
        return list(tickets)
    return [ticket for ticket in tickets if ticket_matches_filters(ticket, filters)]


__all__ = [
    "TicketListFilterValidationError",
    "TicketListFilters",
    "URGENCY_LEVELS",
    "filter_stored_tickets",
    "parse_ticket_list_filters",
    "ticket_matches_filters",
]
