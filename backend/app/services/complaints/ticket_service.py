from datetime import datetime, timezone

from app.database.memory import InMemoryTicketStore, ticket_store
from app.models.ticket import TicketRecord
from app.schemas.ticket import SubmitTicketRequest, SubmitTicketResponse
from app.utils.ticket_ids import (
    generate_ticket_id,
    generate_ticket_number,
    generate_tracking_code,
)

MAX_ID_GENERATION_ATTEMPTS = 10


class TicketService:
    def __init__(self, store: InMemoryTicketStore) -> None:
        self._store = store

    def submit_ticket(self, payload: SubmitTicketRequest) -> SubmitTicketResponse:
        ticket_id = self._generate_unique_ticket_id()
        ticket_number = self._generate_unique_ticket_number()
        tracking_code = self._generate_unique_tracking_code()
        created_at = datetime.now(timezone.utc)

        ticket = TicketRecord(
            ticket_id=ticket_id,
            ticket_number=ticket_number,
            tracking_code=tracking_code,
            status="SUBMITTED",
            description=payload.description,
            language_hint=payload.language_hint,
            contact=payload.contact,
            location=payload.location,
            image_object_key=payload.image_object_key,
            platform=payload.client_metadata.platform,
            app_version=payload.client_metadata.app_version,
            created_at=created_at,
        )
        self._store.save(ticket)

        return SubmitTicketResponse(
            ticketId=ticket.ticket_id,
            ticketNumber=ticket.ticket_number,
            trackingCode=ticket.tracking_code,
            status=ticket.status,
            message="Your report was submitted successfully.",
            createdAt=created_at.isoformat().replace("+00:00", "Z"),
        )

    def _generate_unique_ticket_id(self) -> str:
        for _ in range(MAX_ID_GENERATION_ATTEMPTS):
            ticket_id = generate_ticket_id()
            if self._store.get(ticket_id) is None:
                return ticket_id
        raise RuntimeError("Unable to generate a unique ticket ID.")

    def _generate_unique_ticket_number(self) -> str:
        for _ in range(MAX_ID_GENERATION_ATTEMPTS):
            ticket_number = generate_ticket_number(self._store.next_sequence())
            if not self._store.has_ticket_number(ticket_number):
                return ticket_number
        raise RuntimeError("Unable to generate a unique ticket number.")

    def _generate_unique_tracking_code(self) -> str:
        for _ in range(MAX_ID_GENERATION_ATTEMPTS):
            tracking_code = generate_tracking_code()
            if not self._store.has_tracking_code(tracking_code):
                return tracking_code
        raise RuntimeError("Unable to generate a unique tracking code.")


ticket_service = TicketService(ticket_store)
