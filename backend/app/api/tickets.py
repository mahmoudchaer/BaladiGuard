from fastapi import APIRouter

from app.schemas.ticket import SubmitTicketRequest, SubmitTicketResponse
from app.services.complaints.ticket_service import ticket_service

router = APIRouter(prefix="/v1", tags=["tickets"])


@router.post("/tickets", response_model=SubmitTicketResponse, status_code=201)
def submit_ticket(payload: SubmitTicketRequest) -> SubmitTicketResponse:
    return ticket_service.submit_ticket(payload)
