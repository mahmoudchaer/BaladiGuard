from threading import Lock
from typing import Any

from app.database.ticket_patch import resolve_ticket_attr_name
from app.schemas.stored_ticket import StoredTicket
from app.schemas.ticket_response import TicketStatus


class InMemoryTicketStore:
    def __init__(self) -> None:
        self._tickets: dict[str, StoredTicket] = {}
        self._ticket_numbers: set[str] = set()
        self._tracking_codes: set[str] = set()
        self._sequence = 0
        self._lock = Lock()

    def next_sequence(self) -> int:
        with self._lock:
            self._sequence += 1
            return self._sequence

    def save(self, ticket: StoredTicket) -> None:
        with self._lock:
            self._tickets[ticket.ticket_id] = ticket
            self._ticket_numbers.add(ticket.ticket_number)
            self._tracking_codes.add(ticket.tracking_code)

    def get(self, ticket_id: str) -> StoredTicket | None:
        with self._lock:
            return self._tickets.get(ticket_id)

    def list(self) -> list[StoredTicket]:
        with self._lock:
            return list(self._tickets.values())

    def patch_fields(
        self,
        ticket_id: str,
        fields: dict[str, Any],
    ) -> StoredTicket | None:
        if not fields:
            raise ValueError("At least one field is required for a ticket patch.")
        # Validate field names early (mirrors DynamoDB path).
        for field_name in fields:
            resolve_ticket_attr_name(field_name)

        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                return None
            updated_ticket = ticket.model_copy(update=fields)
            self._tickets[ticket_id] = updated_ticket
            return updated_ticket

    def update_status(
        self,
        ticket_id: str,
        status: TicketStatus,
        updated_at: str,
    ) -> StoredTicket | None:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                return None

            updated_ticket = ticket.model_copy(
                update={
                    "status": status,
                    "updated_at": updated_at,
                },
            )
            self._tickets[ticket_id] = updated_ticket
            return updated_ticket

    def claim_ai_processing(
        self,
        ticket_id: str,
        updated_at: str,
    ) -> StoredTicket | None:
        """Atomically claim a pending ticket for AI work (pending → processing)."""
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None or ticket.ai_processing_status != "pending":
                return None
            updated_ticket = ticket.model_copy(
                update={
                    "ai_processing_status": "processing",
                    "updated_at": updated_at,
                },
            )
            self._tickets[ticket_id] = updated_ticket
            return updated_ticket

    def release_ai_processing_claim(
        self,
        ticket_id: str,
        updated_at: str,
    ) -> StoredTicket | None:
        """Return a stuck processing claim to pending so recovery can reclaim it."""
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None or ticket.ai_processing_status != "processing":
                return None
            updated_ticket = ticket.model_copy(
                update={
                    "ai_processing_status": "pending",
                    "updated_at": updated_at,
                },
            )
            self._tickets[ticket_id] = updated_ticket
            return updated_ticket

    def has_ticket_id(self, ticket_id: str) -> bool:
        with self._lock:
            return ticket_id in self._tickets

    def has_ticket_number(self, ticket_number: str) -> bool:
        with self._lock:
            return ticket_number in self._ticket_numbers

    def has_tracking_code(self, tracking_code: str) -> bool:
        with self._lock:
            return tracking_code in self._tracking_codes

    def clear(self) -> None:
        with self._lock:
            self._tickets.clear()
            self._ticket_numbers.clear()
            self._tracking_codes.clear()
            self._sequence = 0


ticket_store = InMemoryTicketStore()
