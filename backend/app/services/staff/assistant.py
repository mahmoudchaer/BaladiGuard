"""Deterministic, read-only, authorization-grounded staff assistant (#242 / #43)."""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime

from app.core.staff_auth import StaffPrincipal, staff_can_access_ticket
from app.schemas.staff_assistant import StaffAssistantResponse, StaffAssistantTicketReference
from app.schemas.stored_ticket import PENDING_CLASSIFICATION, StoredTicket
from app.services.complaints.sla import derive_ticket_sla
from app.services.staff.assistant_areas import (
    CELL_SIZE_DEGREES,
    MINIMUM_DISTINCT_REPORTS,
    build_area_clusters,
    cell_id_for,
    has_usable_coordinates,
)

_HIGH_PRIORITY_TERMS = (
    "high priority",
    "urgent",
    "critical",
    "critique",
    "عاجل",
    "مستعجل",
    "prioritaire",
)
_REPEATED_AREA_TERMS = (
    "repeated",
    "repeat",
    "area",
    "hotspot",
    "same place",
    "متكرر",
    "منطقة",
    "mouchkil",
    "probl",
)
_NEGATION_PATTERN = re.compile(r"\b(?:do not|don't|not|without|never|no)\b", re.IGNORECASE)
_CONSTRAINT_PATTERN = re.compile(
    r"\b(?:in|near|at|around|before|after|since|on|dans)\s+(?:the\s+)?[a-z0-9]"
    r"|\b(?:today|yesterday|tomorrow|week|month|year|date)\b",
    re.IGNORECASE,
)
_GENERIC_AREA_PATTERN = re.compile(r"\bin\s+(?:an?|the)\s+area\b", re.IGNORECASE)

OPEN_QUEUE_STATUSES = frozenset({"SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS"})
HIGH_PRIORITIES = frozenset({"high", "critical"})
MAX_TICKET_REFERENCES = 20
_SLA_RANK = {
    "overdue": 0,
    "due_soon": 1,
    "on_track": 2,
    "unavailable": 3,
    "completed": 4,
}
_PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _as_of() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _intent(question: str) -> str | None:
    normalized = question.casefold()
    # "in an/the area" is the documented generic repeated-area intent, not a
    # named area filter. Normalize it before rejecting unsupported filters.
    normalized_for_constraints = _GENERIC_AREA_PATTERN.sub("by area", normalized)
    high_priority = any(term in normalized for term in _HIGH_PRIORITY_TERMS)
    repeated_area = any(term in normalized for term in _REPEATED_AREA_TERMS)
    if _NEGATION_PATTERN.search(normalized) or _CONSTRAINT_PATTERN.search(
        normalized_for_constraints
    ):
        return None
    if high_priority == repeated_area:
        return None
    if high_priority:
        return "high_priority_summary"
    if repeated_area:
        return "repeated_area_summary"
    raise AssertionError("intent selection must be exhaustive")


def _category(ticket: StoredTicket) -> str:
    return ticket.final_category or ticket.category


def _department_key(ticket: StoredTicket) -> str:
    return ticket.department_id or "unassigned"


def _is_incomplete(ticket: StoredTicket) -> bool:
    return ticket.category == PENDING_CLASSIFICATION and not ticket.final_category


def _actionability(ticket: StoredTicket) -> tuple:
    sla = derive_ticket_sla(ticket).state
    return (
        _SLA_RANK.get(sla, 9),
        _PRIORITY_RANK.get(ticket.priority or "", 9),
        ticket.created_at,
        ticket.ticket_id,
    )


def _reference(ticket: StoredTicket) -> StaffAssistantTicketReference:
    return StaffAssistantTicketReference(
        ticketId=ticket.ticket_id,
        ticketNumber=ticket.ticket_number,
        status=ticket.status,
        category=_category(ticket),
        priority=ticket.priority,
        slaState=derive_ticket_sla(ticket).state,
        municipalityId=ticket.municipality_id,
        departmentId=ticket.department_id,
        cellId=cell_id_for(ticket),
        duplicateGroupId=ticket.duplicate_group_id,
    )


def _counts(tickets: list[StoredTicket]) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    categories = dict(sorted(Counter(_category(ticket) for ticket in tickets).items()))
    statuses = dict(sorted(Counter(ticket.status for ticket in tickets).items()))
    departments = dict(sorted(Counter(_department_key(ticket) for ticket in tickets).items()))
    return categories, statuses, departments


def _accessible_tickets(principal: StaffPrincipal) -> list[StoredTicket]:
    from app.services.complaints.ticket_service import ticket_service

    return [
        ticket
        for ticket in ticket_service.collect_all_staff_tickets(principal)
        if staff_can_access_ticket(principal, ticket)
    ]


def _open_tickets(tickets: list[StoredTicket]) -> list[StoredTicket]:
    return [ticket for ticket in tickets if ticket.status in OPEN_QUEUE_STATUSES]


class StaffAssistantService:
    """Uses only persisted tickets visible to the authenticated staff principal."""

    def answer(self, question: str, *, principal: StaffPrincipal) -> StaffAssistantResponse:
        intent = _intent(question)
        as_of = _as_of()
        if intent is None:
            return StaffAssistantResponse(
                intent="unsupported",
                asOf=as_of,
                count=0,
                message=(
                    "I can summarize high-priority tickets or repeated problems by area. "
                    "Try asking about urgent tickets or repeated issues in an area."
                ),
            )

        accessible = _open_tickets(_accessible_tickets(principal))
        if intent == "high_priority_summary":
            return self._priority_summary(accessible, as_of)
        return self._repeated_area_summary(accessible, as_of)

    def _priority_summary(
        self, accessible: list[StoredTicket], as_of: str
    ) -> StaffAssistantResponse:
        selected = [ticket for ticket in accessible if ticket.priority in HIGH_PRIORITIES]
        ordered = sorted(selected, key=_actionability)
        categories, statuses, departments = _counts(selected)
        incomplete = sum(1 for ticket in selected if _is_incomplete(ticket))
        if not selected:
            message = (
                "No accessible high-priority or critical tickets in the open operational queue."
            )
        else:
            message = (
                f"{len(selected)} accessible high-priority or critical ticket(s) "
                f"in the open operational queue."
            )
            if incomplete:
                message += f" {incomplete} still pending classification."
        return StaffAssistantResponse(
            intent="high_priority_summary",
            asOf=as_of,
            message=message,
            count=len(selected),
            categories=categories,
            statuses=statuses,
            departments=departments,
            tickets=[_reference(ticket) for ticket in ordered[:MAX_TICKET_REFERENCES]],
            incompleteCount=incomplete,
            appliedFilters={
                "priority": "high,critical",
                "openOnly": "true",
            },
        )

    def _repeated_area_summary(
        self, accessible: list[StoredTicket], as_of: str
    ) -> StaffAssistantResponse:
        located = [ticket for ticket in accessible if has_usable_coordinates(ticket)]
        unlocated = len(accessible) - len(located)
        clusters = build_area_clusters(located)
        selected_ids = {ticket_id for cluster in clusters for ticket_id in cluster.ticket_ids}
        selected = [ticket for ticket in located if ticket.ticket_id in selected_ids]
        ordered = sorted(selected, key=_actionability)
        categories, statuses, departments = _counts(selected)
        incomplete = sum(1 for ticket in selected if _is_incomplete(ticket))
        areas = {cluster.cell_id: cluster.ticket_count for cluster in clusters}
        if not clusters:
            message = (
                "No repeated problem areas in the open operational queue. "
                "Areas need at least two distinct reports in the same 0.002-degree cell."
            )
        else:
            message = (
                f"{len(clusters)} repeated problem area(s) covering {len(selected)} ticket(s). "
                "Duplicate groups count as one report; nearby ungrouped tickets count separately."
            )
        if unlocated:
            message += (
                f" {unlocated} ticket(s) omitted because coordinates are placeholder/unusable."
            )
        if incomplete:
            message += f" {incomplete} still pending classification."
        return StaffAssistantResponse(
            intent="repeated_area_summary",
            asOf=as_of,
            message=message,
            count=len(selected),
            categories=categories,
            statuses=statuses,
            departments=departments,
            areas=areas,
            areaClusters=clusters,
            unlocatedCount=unlocated,
            incompleteCount=incomplete,
            tickets=[_reference(ticket) for ticket in ordered[:MAX_TICKET_REFERENCES]],
            appliedFilters={
                "openOnly": "true",
                "minimumDistinctReports": str(MINIMUM_DISTINCT_REPORTS),
                "cellSizeDegrees": str(CELL_SIZE_DEGREES),
            },
        )


staff_assistant_service = StaffAssistantService()
