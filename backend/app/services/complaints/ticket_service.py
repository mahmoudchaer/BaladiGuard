from datetime import datetime, timezone

from app.database.memory import InMemoryTicketStore, ticket_store
from app.schemas.ticket import SubmitTicketRequest, SubmitTicketResponse
from app.utils.ticket_ids import (
    generate_ticket_id,
    generate_ticket_number,
    generate_tracking_code,
)


class TicketService:
    def __init__(self, store: InMemoryTicketStore) -> None:
        self._store = store

    def submit_ticket(self, payload: SubmitTicketRequest) -> SubmitTicketResponse:
        ticket_id = generate_ticket_id()
        ticket_number = generate_ticket_number(self._store.next_sequence())
        tracking_code = generate_tracking_code()
        created_at = datetime.now(timezone.utc)

        self._store.save(ticket_id, ticket_number, tracking_code)

        return SubmitTicketResponse(
            ticketId=ticket_id,
            ticketNumber=ticket_number,
            trackingCode=tracking_code,
            status="SUBMITTED",
            message="Your report was submitted successfully.",
            createdAt=created_at.isoformat().replace("+00:00", "Z"),
        )


ticket_service = TicketService(ticket_store)
