from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from app.core.errors import build_error_response, get_request_id
from app.core.staff_auth import StaffDep
from app.schemas.ticket import SubmitTicketRequest, SubmitTicketResponse
from app.schemas.ticket_ai_update import ReviewTicketCategoryRequest
from app.schemas.ticket_merge import MergeDuplicateTicketsRequest
from app.schemas.ticket_response import (
    CitizenTicketResponse,
    TicketResponse,
    UpdateTicketStatusRequest,
)
from app.services.complaints.status_workflow import InvalidStatusTransitionError
from app.services.complaints.ticket_service import (
    DuplicateMergeError,
    TicketNotFoundError,
    ticket_service,
)

router = APIRouter(prefix="/v1", tags=["tickets"])


@router.post("/tickets", response_model=SubmitTicketResponse, status_code=201)
def submit_ticket(
    payload: SubmitTicketRequest,
    background_tasks: BackgroundTasks,
) -> SubmitTicketResponse:
    """Public citizen submission — no staff auth required."""
    response = ticket_service.submit_ticket(payload)
    background_tasks.add_task(ticket_service.process_ticket_ai, response.ticket_id)
    return response


@router.get("/tickets", response_model=list[TicketResponse])
def list_tickets(_: StaffDep) -> list[TicketResponse]:
    """Staff dashboard ticket list (issue #72)."""
    return ticket_service.list_tickets()


@router.get("/tickets/track/{tracking_code}", response_model=CitizenTicketResponse)
def get_ticket_by_tracking_code(
    tracking_code: str,
    request: Request,
) -> CitizenTicketResponse | JSONResponse:
    """Public citizen tracking lookup — no staff auth required."""
    ticket = ticket_service.get_ticket_by_tracking_code(tracking_code)
    if ticket is None:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    return ticket


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: str,
    request: Request,
    _: StaffDep,
) -> TicketResponse | JSONResponse:
    """Staff ticket detail (issue #72). Auth is checked before any ticket lookup
    so unauthorized callers never learn whether an ID exists.
    """
    ticket = ticket_service.get_ticket(ticket_id)
    if ticket is None:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    return ticket


@router.patch("/tickets/{ticket_id}/status", response_model=TicketResponse)
def update_ticket_status(
    ticket_id: str,
    payload: UpdateTicketStatusRequest,
    request: Request,
    _: StaffDep,
) -> TicketResponse | JSONResponse:
    try:
        return ticket_service.update_ticket_status(ticket_id, payload)
    except TicketNotFoundError:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    except InvalidStatusTransitionError as exc:
        return build_error_response(
            code="INVALID_STATUS_TRANSITION",
            message=str(exc),
            request_id=get_request_id(request),
            status_code=400,
        )


@router.patch("/tickets/{ticket_id}/category", response_model=TicketResponse)
def review_ticket_category(
    ticket_id: str,
    payload: ReviewTicketCategoryRequest,
    request: Request,
    _: StaffDep,
) -> TicketResponse | JSONResponse:
    try:
        return ticket_service.review_ticket_category(ticket_id, payload)
    except TicketNotFoundError:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )


@router.post("/tickets/merge", response_model=TicketResponse)
def merge_duplicate_tickets(
    payload: MergeDuplicateTicketsRequest,
    request: Request,
    _: StaffDep,
) -> TicketResponse | JSONResponse:
    try:
        return ticket_service.merge_duplicate_tickets(payload)
    except TicketNotFoundError:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="One or more tickets were not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    except DuplicateMergeError as exc:
        return build_error_response(
            code="VALIDATION_ERROR",
            message=str(exc),
            request_id=get_request_id(request),
            status_code=400,
        )
