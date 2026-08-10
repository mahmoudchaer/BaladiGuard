"""Deterministic, read-only, authorization-grounded staff assistant (#242)."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from app.core.staff_auth import StaffPrincipal, staff_can_access_ticket
from app.database.store_factory import get_ticket_store
from app.schemas.staff_assistant import StaffAssistantResponse, StaffAssistantTicketReference
from app.schemas.stored_ticket import StoredTicket

_HIGH_PRIORITY_TERMS = (
    "high priority",
    "urgent",
    "critical",
    "عاجل",
    "مستعجل",
    "urgent",
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


def _as_of() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _intent(question: str) -> str | None:
    normalized = question.casefold()
    if any(term in normalized for term in _HIGH_PRIORITY_TERMS):
        return "high_priority_summary"
    if any(term in normalized for term in _REPEATED_AREA_TERMS):
        return "repeated_area_summary"
    return None


def _area(ticket: StoredTicket) -> str:
    return (ticket.location.address_text or "Unspecified area").strip() or "Unspecified area"


def _reference(ticket: StoredTicket) -> StaffAssistantTicketReference:
    return StaffAssistantTicketReference(
        ticketId=ticket.ticket_id,
        ticketNumber=ticket.ticket_number,
        category=ticket.final_category or ticket.category,
        priority=ticket.priority,
        municipalityId=ticket.municipality_id,
        departmentId=ticket.department_id,
    )


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

        accessible = [
            ticket
            for ticket in get_ticket_store().list()
            if staff_can_access_ticket(principal, ticket)
        ]
        if intent == "high_priority_summary":
            selected = [ticket for ticket in accessible if ticket.priority in {"high", "critical"}]
            filters = {"priority": "high,critical"}
            message = f"{len(selected)} accessible high-priority or critical ticket(s)."
        else:
            grouped = Counter(_area(ticket) for ticket in accessible)
            repeated_areas = {area for area, count in grouped.items() if count >= 2}
            selected = [ticket for ticket in accessible if _area(ticket) in repeated_areas]
            filters = {"minimumTicketsPerArea": "2"}
            message = f"{len(selected)} accessible ticket(s) in repeated area(s)."

        categories = dict(
            sorted(Counter(ticket.final_category or ticket.category for ticket in selected).items())
        )
        areas = dict(sorted(Counter(_area(ticket) for ticket in selected).items()))
        ordered = sorted(
            selected, key=lambda ticket: (ticket.created_at, ticket.ticket_id), reverse=True
        )
        return StaffAssistantResponse(
            intent=intent,
            asOf=as_of,
            message=message,
            count=len(selected),
            categories=categories,
            areas=areas,
            tickets=[_reference(ticket) for ticket in ordered[:20]],
            appliedFilters=filters,
        )


staff_assistant_service = StaffAssistantService()
