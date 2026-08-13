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
    ) -> TicketHistoryPage: ...

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
        self, ticket_id: str, generation: int, updated_at: str
    ) -> StoredTicket | None: ...

    def start_image_reprocessing(self, ticket_id: str, updated_at: str) -> StoredTicket | None: ...

    def has_ticket_id(self, ticket_id: str) -> bool: ...

    def has_ticket_number(self, ticket_number: str) -> bool: ...

    def has_tracking_code(self, tracking_code: str) -> bool: ...

    def clear(self) -> None: ...
