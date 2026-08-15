"""Ticket list query filters for staff dashboard reads (issue #142)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from app.schemas.stored_ticket import ReportPriority, StoredTicket
from app.schemas.ticket_status import TICKET_STATUSES, TicketStatus, is_known_ticket_status
from app.services.ai.categories import allowed_category_ids
from app.services.complaints.sla import derive_ticket_sla
from app.services.routing import department_ids

URGENCY_LEVELS: tuple[ReportPriority, ...] = ("low", "medium", "high", "critical")
SLA_STATES = frozenset({"on_track", "due_soon", "overdue", "completed", "unavailable"})
ASSIGNMENT_STATES = frozenset({"assigned", "unassigned"})
MAX_SEARCH_QUERY_LENGTH = 80
MAX_TICKET_IDS = 20
MAX_TICKET_ID_LENGTH = 80
OPEN_TICKET_STATUSES: frozenset[TicketStatus] = frozenset(
    {"SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS"}
)


@dataclass(frozen=True, slots=True)
class TicketListFilters:
    """Optional AND-combined filters over persisted ticket fields."""

    status: TicketStatus | None = None
    category: str | None = None
    urgency: tuple[ReportPriority, ...] | None = None
    department_id: str | None = None
    sla_state: str | None = None
    assignment_state: Literal["assigned", "unassigned"] | None = None
    worker_id: str | None = None
    team_id: str | None = None
    workforce_unassigned: bool = False
    q: str | None = None
    open_only: bool = False
    ticket_ids: tuple[str, ...] | None = None


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
    sla_state: str | None = None,
    assignment_state: str | None = None,
    worker_id: str | None = None,
    team_id: str | None = None,
    workforce_unassigned: bool = False,
    q: str | None = None,
    open_only: bool = False,
    ticket_ids: str | None = None,
) -> tuple[TicketListFilters | None, list[TicketListFilterValidationError]]:
    """Validate raw query values and build filters.

    Omitted / null values mean \"no filter\". Blank strings are rejected so callers
    cannot accidentally treat whitespace as a match key.
    """

    errors: list[TicketListFilterValidationError] = []
    parsed_status: TicketStatus | None = None
    parsed_category: str | None = None
    parsed_urgency: tuple[ReportPriority, ...] | None = None
    parsed_department_id: str | None = None
    parsed_sla_state: str | None = None
    parsed_assignment_state: Literal["assigned", "unassigned"] | None = None
    parsed_worker_id: str | None = None
    parsed_team_id: str | None = None
    parsed_q: str | None = None
    parsed_ticket_ids: tuple[str, ...] | None = None

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
        parts = [part.strip().lower() for part in urgency.split(",")]
        if not urgency.strip() or any(not part for part in parts):
            errors.append(
                TicketListFilterValidationError(
                    field="urgency",
                    message="Urgency filter must not be empty.",
                )
            )
        else:
            unique: list[ReportPriority] = []
            unknown = False
            for part in parts:
                if part not in URGENCY_LEVELS:
                    unknown = True
                    continue
                level = cast(ReportPriority, part)
                if level not in unique:
                    unique.append(level)
            if unknown:
                supported = ", ".join(URGENCY_LEVELS)
                errors.append(
                    TicketListFilterValidationError(
                        field="urgency",
                        message=(
                            f"Urgency must be one of: {supported}, or a comma-separated subset."
                        ),
                    )
                )
            else:
                parsed_urgency = tuple(sorted(unique, key=URGENCY_LEVELS.index))

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

    if sla_state is not None:
        normalized_sla_state = sla_state.strip().lower()
        if normalized_sla_state not in SLA_STATES:
            errors.append(
                TicketListFilterValidationError(
                    field="slaState",
                    message="SLA state must be one of: " + ", ".join(sorted(SLA_STATES)) + ".",
                )
            )
        else:
            parsed_sla_state = normalized_sla_state

    if assignment_state is not None:
        normalized_assignment = assignment_state.strip().lower()
        if normalized_assignment not in ASSIGNMENT_STATES:
            errors.append(
                TicketListFilterValidationError(
                    field="assignmentState",
                    message="Assignment state must be one of: assigned, unassigned.",
                )
            )
        else:
            parsed_assignment_state = cast(Literal["assigned", "unassigned"], normalized_assignment)

    if worker_id is not None:
        parsed_worker_id = worker_id.strip()
        if not parsed_worker_id:
            errors.append(
                TicketListFilterValidationError(
                    field="workerId",
                    message="Worker filter must not be empty.",
                )
            )
    if team_id is not None:
        parsed_team_id = team_id.strip()
        if not parsed_team_id:
            errors.append(
                TicketListFilterValidationError(
                    field="teamId",
                    message="Team filter must not be empty.",
                )
            )
    if parsed_worker_id and parsed_team_id:
        errors.append(
            TicketListFilterValidationError(
                field="workerId",
                message="Filter by workerId or teamId, not both.",
            )
        )
    if workforce_unassigned and (parsed_worker_id or parsed_team_id):
        errors.append(
            TicketListFilterValidationError(
                field="workforceUnassigned",
                message="workforceUnassigned cannot be combined with workerId or teamId.",
            )
        )

    if q is not None:
        normalized_q = q.strip()
        if not normalized_q:
            errors.append(
                TicketListFilterValidationError(
                    field="q",
                    message="Search query must not be empty.",
                )
            )
        elif len(normalized_q) > MAX_SEARCH_QUERY_LENGTH:
            errors.append(
                TicketListFilterValidationError(
                    field="q",
                    message=f"Search query must be at most {MAX_SEARCH_QUERY_LENGTH} characters.",
                )
            )
        else:
            parsed_q = normalized_q

    if ticket_ids is not None:
        parts = [part.strip() for part in ticket_ids.split(",")]
        if not ticket_ids.strip() or any(not part for part in parts):
            errors.append(
                TicketListFilterValidationError(
                    field="ticketIds",
                    message="ticketIds must be a comma-separated list of ticket ids.",
                )
            )
        elif len(parts) > MAX_TICKET_IDS:
            errors.append(
                TicketListFilterValidationError(
                    field="ticketIds",
                    message=f"ticketIds accepts at most {MAX_TICKET_IDS} ids.",
                )
            )
        elif any(len(part) > MAX_TICKET_ID_LENGTH for part in parts):
            errors.append(
                TicketListFilterValidationError(
                    field="ticketIds",
                    message=f"Each ticket id must be at most {MAX_TICKET_ID_LENGTH} characters.",
                )
            )
        else:
            unique: list[str] = []
            for part in parts:
                if part not in unique:
                    unique.append(part)
            parsed_ticket_ids = tuple(unique)

    if errors:
        return None, errors

    return (
        TicketListFilters(
            status=parsed_status,
            category=parsed_category,
            urgency=parsed_urgency,
            department_id=parsed_department_id,
            sla_state=parsed_sla_state,
            assignment_state=parsed_assignment_state,
            worker_id=parsed_worker_id,
            team_id=parsed_team_id,
            workforce_unassigned=workforce_unassigned,
            q=parsed_q,
            open_only=open_only,
            ticket_ids=parsed_ticket_ids,
        ),
        [],
    )


def ticket_matches_filters(ticket: StoredTicket, filters: TicketListFilters) -> bool:
    """Return True when a ticket matches every provided persisted-field filter."""

    if filters.status is not None and ticket.status != filters.status:
        return False
    if filters.open_only and ticket.status not in OPEN_TICKET_STATUSES:
        return False
    if filters.category is not None and ticket.category != filters.category:
        return False
    if filters.urgency is not None and ticket.priority not in filters.urgency:
        return False
    if filters.department_id is not None and ticket.department_id != filters.department_id:
        return False
    if filters.sla_state is not None and derive_ticket_sla(ticket).state != filters.sla_state:
        return False
    if filters.assignment_state == "unassigned" and ticket.department_id is not None:
        return False
    if filters.assignment_state == "assigned" and ticket.department_id is None:
        return False
    if filters.worker_id is not None and ticket.assigned_worker_id != filters.worker_id:
        return False
    if filters.team_id is not None and ticket.assigned_team_id != filters.team_id:
        return False
    if filters.workforce_unassigned and (ticket.assigned_worker_id or ticket.assigned_team_id):
        return False
    if filters.ticket_ids is not None and ticket.ticket_id not in filters.ticket_ids:
        return False
    if filters.q is not None:
        needle = filters.q.casefold()
        haystack = " ".join(
            part
            for part in (
                ticket.ticket_id,
                ticket.ticket_number,
                ticket.description,
                ticket.location.address_text if ticket.location else "",
            )
            if part
        ).casefold()
        if needle not in haystack:
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
    "SLA_STATES",
    "ASSIGNMENT_STATES",
    "MAX_SEARCH_QUERY_LENGTH",
    "MAX_TICKET_IDS",
    "filter_stored_tickets",
    "parse_ticket_list_filters",
    "ticket_matches_filters",
]
