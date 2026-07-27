from typing import Any, Protocol

from app.schemas.stored_ticket import StoredTicket
from app.schemas.ticket_response import TicketStatus


class TicketStore(Protocol):
    def next_sequence(self) -> int: ...

    def save(self, ticket: StoredTicket) -> None: ...

    def get(self, ticket_id: str) -> StoredTicket | None: ...

    def get_by_tracking_code(self, tracking_code: str) -> StoredTicket | None: ...

    def list(self) -> list[StoredTicket]: ...

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
    ) -> StoredTicket | None: ...

    def release_ai_processing_claim(
        self,
        ticket_id: str,
        updated_at: str,
    ) -> StoredTicket | None: ...

    def has_ticket_id(self, ticket_id: str) -> bool: ...

    def has_ticket_number(self, ticket_number: str) -> bool: ...

    def has_tracking_code(self, tracking_code: str) -> bool: ...

    def clear(self) -> None: ...
