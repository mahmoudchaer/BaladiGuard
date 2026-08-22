"""Shared operational ticket buckets for workload and dashboard aggregates (#318)."""

from __future__ import annotations

from collections.abc import Iterable

from app.schemas.stored_ticket import StoredTicket
from app.services.complaints.sla import derive_ticket_sla
from app.services.complaints.ticket_list_filters import OPEN_TICKET_STATUSES

QUEUED_STATUSES = frozenset({"SUBMITTED", "UNDER_REVIEW"})
ASSIGNED_STATUSES = frozenset({"ASSIGNED"})
IN_PROGRESS_STATUSES = frozenset({"IN_PROGRESS"})
COMPLETED_STATUSES = frozenset({"RESOLVED", "CLOSED"})


def is_workforce_unassigned(ticket: StoredTicket) -> bool:
    return not ticket.assigned_worker_id and not ticket.assigned_team_id


def is_department_unassigned(ticket: StoredTicket) -> bool:
    return ticket.department_id is None


def is_cancelled_ticket(ticket: StoredTicket) -> bool:
    """Closed without a recorded citizen resolution (rejected / withdrawn)."""
    return ticket.status == "CLOSED" and ticket.resolved_at is None


def count_operational_buckets(tickets: Iterable[StoredTicket]) -> dict[str, int]:
    queued = 0
    assigned = 0
    in_progress = 0
    due_soon = 0
    overdue = 0
    completed = 0
    cancelled = 0
    open_count = 0
    workforce_unassigned = 0
    department_unassigned = 0
    critical = 0
    high = 0
    for ticket in tickets:
        if ticket.status in OPEN_TICKET_STATUSES:
            open_count += 1
            if is_workforce_unassigned(ticket):
                workforce_unassigned += 1
        if ticket.status in QUEUED_STATUSES:
            queued += 1
        elif ticket.status in ASSIGNED_STATUSES:
            assigned += 1
        elif ticket.status in IN_PROGRESS_STATUSES:
            in_progress += 1
        if ticket.status in COMPLETED_STATUSES:
            completed += 1
        if is_cancelled_ticket(ticket):
            cancelled += 1
        if is_department_unassigned(ticket):
            department_unassigned += 1
        if ticket.priority == "critical":
            critical += 1
        elif ticket.priority == "high":
            high += 1
        sla_state = derive_ticket_sla(ticket).state
        if sla_state == "due_soon":
            due_soon += 1
        elif sla_state == "overdue":
            overdue += 1
    return {
        "queued": queued,
        "assigned": assigned,
        "in_progress": in_progress,
        "due_soon": due_soon,
        "overdue": overdue,
        "completed": completed,
        "cancelled": cancelled,
        "open_count": open_count,
        "workforce_unassigned": workforce_unassigned,
        "department_unassigned": department_unassigned,
        "critical": critical,
        "high": high,
    }
