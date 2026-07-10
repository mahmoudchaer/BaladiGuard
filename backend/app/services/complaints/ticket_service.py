from datetime import UTC, datetime

from app.database.status_history_store import StatusHistoryStore
from app.database.store_factory import get_status_history_store, get_ticket_store
from app.database.ticket_store import TicketStore
from app.schemas.stored_status_history import StoredStatusHistory
from app.schemas.stored_ticket import PENDING_CLASSIFICATION, StoredTicket
from app.schemas.ticket import SubmitTicketRequest, SubmitTicketResponse
from app.schemas.ticket_response import TicketResponse, UpdateTicketStatusRequest
from app.schemas.ticket_status import TicketStatus
from app.services.complaints.status_workflow import validate_status_transition
from app.services.complaints.ticket_read_mapper import map_ticket_to_response
from app.utils.ticket_ids import (
    generate_status_history_id,
    generate_ticket_id,
    generate_ticket_number,
    generate_tracking_code,
)


class TicketNotFoundError(LookupError):
    pass


class TicketService:
    def __init__(self, store: TicketStore, history_store: StatusHistoryStore) -> None:
        self._store = store
        self._history_store = history_store

    def submit_ticket(self, payload: SubmitTicketRequest) -> SubmitTicketResponse:
        ticket_id = generate_ticket_id()
        ticket_number = generate_ticket_number(self._store.next_sequence())
        tracking_code = generate_tracking_code()
        created_at = datetime.now(UTC)
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
        self._record_status_history(
            ticket_id=ticket_id,
            previous_status=None,
            new_status="SUBMITTED",
            updated_by=None,
            note="Ticket submitted.",
            created_at=created_at_iso,
        )

        return SubmitTicketResponse(
            ticketId=ticket_id,
            ticketNumber=ticket_number,
            trackingCode=tracking_code,
            status="SUBMITTED",
            message="Your report was submitted successfully.",
            createdAt=created_at_iso,
        )

    def list_tickets(self) -> list[TicketResponse]:
        tickets = sorted(
            self._store.list(),
            key=lambda ticket: (ticket.created_at, ticket.ticket_number),
            reverse=True,
        )
        return [self._map_ticket(ticket) for ticket in tickets]

    def get_ticket(self, ticket_id: str) -> TicketResponse | None:
        ticket = self._store.get(ticket_id)
        if ticket is None:
            return None
        return self._map_ticket(ticket)

    def update_ticket_status(
        self,
        ticket_id: str,
        payload: UpdateTicketStatusRequest,
    ) -> TicketResponse:
        ticket = self._store.get(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(ticket_id)

        validate_status_transition(ticket.status, payload.status)

        updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        updated_ticket = ticket.model_copy(
            update={
                "status": payload.status,
                "updated_at": updated_at,
                "updated_by": payload.updated_by,
            }
        )
        self._store.save(updated_ticket)
        self._record_status_history(
            ticket_id=ticket_id,
            previous_status=ticket.status,
            new_status=payload.status,
            updated_by=payload.updated_by,
            note=payload.note,
            created_at=updated_at,
        )
        return self._map_ticket(updated_ticket)

    def _map_ticket(self, ticket: StoredTicket) -> TicketResponse:
        history = self._history_store.list_by_ticket_id(ticket.ticket_id)
        return map_ticket_to_response(ticket, history)

    def _record_status_history(
        self,
        *,
        ticket_id: str,
        previous_status: TicketStatus | None,
        new_status: TicketStatus,
        updated_by: str | None,
        note: str | None,
        created_at: str,
    ) -> None:
        entry = StoredStatusHistory(
            historyId=generate_status_history_id(),
            ticketId=ticket_id,
            previousStatus=previous_status,
            newStatus=new_status,
            updatedBy=updated_by,
            note=note,
            createdAt=created_at,
        )
        self._history_store.append(entry)


ticket_service = TicketService(get_ticket_store(), get_status_history_store())
