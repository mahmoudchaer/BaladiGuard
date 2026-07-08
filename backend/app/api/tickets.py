from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.errors import build_error_response, get_request_id
from app.schemas.ticket import SubmitTicketRequest, SubmitTicketResponse
from app.schemas.ticket_response import TicketResponse
from app.services.complaints.ticket_service import ticket_service

router = APIRouter(prefix="/v1", tags=["tickets"])


@router.post("/tickets", response_model=SubmitTicketResponse, status_code=201)
def submit_ticket(payload: SubmitTicketRequest) -> SubmitTicketResponse:
    return ticket_service.submit_ticket(payload)


@router.get("/tickets", response_model=list[TicketResponse])
def list_tickets() -> list[TicketResponse]:
    return ticket_service.list_tickets()


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: str, request: Request) -> TicketResponse | JSONResponse:
    ticket = ticket_service.get_ticket(ticket_id)
    if ticket is None:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    return ticket
