from datetime import datetime, timezone

from app.database.store_factory import get_ticket_store
from app.database.ticket_store import TicketStore
from app.schemas.stored_ticket import PENDING_CLASSIFICATION, StoredTicket
from app.schemas.ticket import SubmitTicketRequest, SubmitTicketResponse
from app.utils.ticket_ids import (
    generate_ticket_id,
    generate_ticket_number,
    generate_tracking_code,
)


class TicketService:
    def __init__(self, store: TicketStore) -> None:
        self._store = store

    def submit_ticket(self, payload: SubmitTicketRequest) -> SubmitTicketResponse:
        ticket_id = generate_ticket_id()
        ticket_number = generate_ticket_number(self._store.next_sequence())
        tracking_code = generate_tracking_code()
        created_at = datetime.now(timezone.utc)
        created_at_iso = created_at.isoformat().replace("+00:00", "Z")

        stored_ticket = StoredTicket(
            ticketId=ticket_id,
            ticketNumber=ticket_number,
            trackingCode=tracking_code,
            description=payload.description,
            contact=payload.contact,
            location=payload.location,
            imageObjectKey=payload.image_object_key,
            status="SUBMITTED",
            category=PENDING_CLASSIFICATION,
            createdAt=created_at_iso,
            updatedAt=created_at_iso,
        )
        self._store.save(stored_ticket)

        return SubmitTicketResponse(
            ticketId=ticket_id,
            ticketNumber=ticket_number,
            trackingCode=tracking_code,
            status="SUBMITTED",
            message="Your report was submitted successfully.",
            createdAt=created_at_iso,
        )


ticket_service = TicketService(get_ticket_store())
