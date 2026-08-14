from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.schemas.stored_ticket import StoredTicket
from app.schemas.ticket_response import TicketStatus


@dataclass(frozen=True)
class TicketHistoryPage:
    items: list[StoredTicket]
    next_cursor: str | None


@dataclass(frozen=True)
class StaffTicketPage:
    items: list[StoredTicket]
    next_cursor: str | None
    scanned_count: int


def public_ticket_matches_query(
    ticket: StoredTicket,
    *,
    q: str | None = None,
    status: TicketStatus | None = None,
    category: str | None = None,
    north: float | None = None,
    south: float | None = None,
    east: float | None = None,
    west: float | None = None,
) -> bool:
    """Apply public discovery predicates before pagination limits are imposed."""
    effective_category = (ticket.final_category or ticket.category or "").casefold()
    if status is not None and ticket.status != status:
        return False
    if category and effective_category != category.strip().casefold():
        return False
    if q:
        searchable = " ".join(
            (
                ticket.ticket_number,
                ticket.public_description or "",
                ticket.public_location_label or "",
                effective_category.replace("_", " "),
            )
        ).casefold()
        if q.strip().casefold() not in searchable:
            return False

    bounds = (north, south, east, west)
    if not any(value is not None for value in bounds):
        return True
    if any(value is None for value in bounds):
        raise ValueError("Public viewport bounds must be provided together.")
    assert north is not None and south is not None
    assert east is not None and west is not None
    if ticket.location.latitude > north or ticket.location.latitude < south:
        return False
    if west <= east:
        return west <= ticket.location.longitude <= east
    return ticket.location.longitude >= west or ticket.location.longitude <= east


class TicketStore(Protocol):
    def next_sequence(self) -> int: ...

    def save(self, ticket: StoredTicket) -> None: ...

    def get(self, ticket_id: str) -> StoredTicket | None: ...

    def get_by_tracking_code(self, tracking_code: str) -> StoredTicket | None: ...

    def get_by_ticket_number(self, ticket_number: str) -> StoredTicket | None: ...

    def list(self) -> list[StoredTicket]: ...

    def list_staff_page(
        self,
        *,
        browse_mode: Literal["admin", "municipality"],
        municipality_id: str | None,
        department_ids: list[str] | None,
        limit: int,
        cursor: str | None,
        status: str | None = None,
        category: str | None = None,
        urgency: str | None = None,
        department_id: str | None = None,
        assignment_state: Literal["assigned", "unassigned"] | None = None,
        q: str | None = None,
        open_only: bool = False,
    ) -> StaffTicketPage: ...

    def staff_continuation_cursor(
        self,
        ticket: StoredTicket,
        *,
        browse_mode: Literal["admin", "municipality"],
        municipality_id: str | None,
        department_id: str | None = None,
    ) -> str: ...

    def list_public(
        self,
        *,
        limit: int,
        cursor: str | None = None,
        q: str | None = None,
        status: TicketStatus | None = None,
        category: str | None = None,
        north: float | None = None,
        south: float | None = None,
        east: float | None = None,
        west: float | None = None,
    ) -> TicketHistoryPage: ...

    def public_continuation_cursor(self, ticket: StoredTicket) -> str: ...

    def list_by_owner(
        self,
        owner_user_id: str,
        *,
        limit: int,
        cursor: str | None = None,
    ) -> TicketHistoryPage: ...

    def patch_fields(
        self,
        ticket_id: str,
        fields: dict[str, Any],
    ) -> StoredTicket | None: ...

    def update_status(
        self,
        ticket_id: str,
        status: TicketStatus,
        updated_at: str,
    ) -> StoredTicket | None: ...

    def claim_ai_processing(
        self,
        ticket_id: str,
        updated_at: str,
        claim_token: str | None = None,
    ) -> StoredTicket | None: ...

    def release_ai_processing_claim(
        self,
        ticket_id: str,
        updated_at: str,
    ) -> StoredTicket | None: ...

    def requeue_ai_processing(self, ticket_id: str, updated_at: str) -> StoredTicket | None: ...

    def patch_ai_fields(
        self, ticket_id: str, claim_token: str, fields: dict[str, object]
    ) -> StoredTicket | None: ...

    def claim_image_redaction(
        self, ticket_id: str, generation: int, claim_token: str, updated_at: str
    ) -> StoredTicket | None: ...

    def finalize_image_redaction(
        self, ticket_id: str, generation: int, claim_token: str, fields: dict[str, Any]
    ) -> StoredTicket | None: ...

    def requeue_image_redaction(
        self, ticket_id: str, generation: int, claim_token: str, updated_at: str
    ) -> StoredTicket | None: ...

    def start_image_reprocessing(self, ticket_id: str, updated_at: str) -> StoredTicket | None: ...

    def apply_image_redaction_review(
        self,
        ticket_id: str,
        *,
        expected_generation: int,
        expected_status: str,
        expected_candidate_revision: int,
        fields: dict[str, Any],
        copy_candidate_to_public: bool = False,
    ) -> StoredTicket | None: ...

    def has_ticket_id(self, ticket_id: str) -> bool: ...

    def has_ticket_number(self, ticket_number: str) -> bool: ...

    def has_tracking_code(self, tracking_code: str) -> bool: ...

    def clear(self) -> None: ...
