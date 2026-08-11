import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import ContributionReadyCitizenDep, StaffActorDep
from app.core.citizen_auth import unauthorized
from app.core.errors import ErrorDetail, build_error_response, get_request_id
from app.core.rate_limit import enforce_rate_limit
from app.core.staff_auth import StaffDep
from app.database.store_factory import get_citizen_store
from app.schemas.staff_assistant import StaffAssistantQuery, StaffAssistantResponse
from app.schemas.ticket import SubmitTicketRequest, SubmitTicketResponse
from app.schemas.ticket_ai_update import AssignTicketDepartmentRequest, ReviewTicketCategoryRequest
from app.schemas.ticket_merge import MergeDuplicateTicketsRequest
from app.schemas.ticket_response import (
    CitizenTicketResponse,
    PublicTicketListResponse,
    PublicTicketResponse,
    TicketResponse,
    UpdateTicketPublicContentRequest,
    UpdateTicketStatusRequest,
)
from app.services.ai_job_queue import ai_job_queue
from app.services.citizens.service import snapshot_contact_for_ticket
from app.services.complaints.status_workflow import (
    InvalidStatusTransitionError,
    MissingDepartmentAssignmentError,
)
from app.services.complaints.ticket_list_filters import parse_ticket_list_filters
from app.services.complaints.ticket_service import (
    DuplicateMergeError,
    PublicContentUpdateError,
    StaffScopeForbiddenError,
    TicketNotFoundError,
    TicketSubmissionInProgressError,
    ticket_service,
)
from app.services.staff.assistant import staff_assistant_service
from app.utils.ticket_ids import is_valid_tracking_code

router = APIRouter(prefix="/v1", tags=["tickets"])
logger = logging.getLogger(__name__)


@router.post("/staff-assistant/query", response_model=StaffAssistantResponse)
def query_staff_assistant(
    payload: StaffAssistantQuery,
    principal: StaffDep,
) -> StaffAssistantResponse:
    """Read-only deterministic assistant, grounded in the caller's visible tickets."""
    return staff_assistant_service.answer(payload.question, principal=principal)


@router.post("/tickets", response_model=SubmitTicketResponse, status_code=201)
def submit_ticket(
    payload: SubmitTicketRequest,
    request: Request,
    principal: ContributionReadyCitizenDep,
) -> SubmitTicketResponse | JSONResponse:
    """Contribution-ready citizen submission — guests and incomplete profiles are rejected."""
    limited = enforce_rate_limit(
        request,
        "public-ticket-submission",
        message="Too many public ticket requests. Please wait before trying again.",
    )
    if limited is not None:
        return limited

    user = get_citizen_store().get(principal.user_id)
    if user is None:
        raise unauthorized(request)

    # Prefer Idempotency-Key header; body clientSubmissionId is a fallback (issue #258).
    header_key = (request.headers.get("Idempotency-Key") or "").strip() or None
    client_submission_key = header_key or payload.client_submission_id

    try:
        response = ticket_service.submit_ticket(
            payload,
            owner_user_id=principal.user_id,
            contact=snapshot_contact_for_ticket(user),
            client_submission_key=client_submission_key,
        )
    except TicketSubmissionInProgressError as exc:
        return build_error_response(
            code="SUBMISSION_IN_PROGRESS",
            message=str(exc),
            request_id=get_request_id(request),
            details=[ErrorDetail(field="Idempotency-Key", message=str(exc))],
            status_code=409,
        )

    try:
        ai_job_queue.enqueue(response.ticket_id)
    except Exception as exc:
        # The persisted pending ticket is the durable outbox record. Returning
        # success prevents a client retry from creating a duplicate report;
        # the worker reconciles pending tickets into queue rows on every poll.
        logger.warning(
            "AI queue write deferred to outbox reconciliation ticket_id=%s error=%s",
            response.ticket_id,
            type(exc).__name__,
        )
    return response


@router.get("/tickets", response_model=list[TicketResponse])
def list_tickets(
    principal: StaffDep,
    request: Request,
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    urgency: str | None = Query(default=None),
    department_id: str | None = Query(default=None, alias="departmentId"),
    sla_state: str | None = Query(default=None, alias="slaState"),
) -> list[TicketResponse] | JSONResponse:
    """Staff dashboard ticket list with optional persisted-field filters (issue #142)."""
    filters, errors = parse_ticket_list_filters(
        status=status,
        category=category,
        urgency=urgency,
        department_id=department_id,
        sla_state=sla_state,
    )
    if errors:
        return build_error_response(
            code="VALIDATION_ERROR",
            message="The request contains invalid fields.",
            request_id=get_request_id(request),
            details=[ErrorDetail(field=error.field, message=error.message) for error in errors],
            status_code=400,
        )
    return ticket_service.list_tickets(filters, staff_principal=principal)


@router.get("/tickets/track/{tracking_code}", response_model=CitizenTicketResponse)
def get_ticket_by_tracking_code(
    tracking_code: str,
    request: Request,
) -> CitizenTicketResponse | JSONResponse:
    """Public citizen tracking lookup (issue #140). No staff auth required."""
    limited = enforce_rate_limit(
        request,
        "public-ticket-tracking",
        message="Too many public ticket requests. Please wait before trying again.",
    )
    if limited is not None:
        return limited

    if not is_valid_tracking_code(tracking_code):
        return build_error_response(
            code="VALIDATION_ERROR",
            message="The tracking code format is invalid.",
            request_id=get_request_id(request),
            details=[
                ErrorDetail(
                    field="trackingCode",
                    message=(
                        "Tracking codes must be 6 characters using A-Z and 2-9, "
                        "excluding I, O, 0, and 1."
                    ),
                )
            ],
            status_code=400,
        )

    ticket = ticket_service.get_ticket_by_tracking_code(tracking_code)
    if ticket is None:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    return ticket


@router.get("/tickets/public", response_model=PublicTicketListResponse)
def list_public_tickets(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
) -> PublicTicketListResponse | JSONResponse:
    """Unauthenticated citizen-safe public report feed for map/list browsing."""
    limited = enforce_rate_limit(
        request,
        "public-ticket-browsing",
        message="Too many public ticket requests. Please wait before trying again.",
    )
    if limited is not None:
        return limited

    try:
        return ticket_service.list_public_tickets(limit=limit, cursor=cursor)
    except ValueError:
        return build_error_response(
            code="VALIDATION_ERROR",
            message="The public report cursor is invalid.",
            request_id=get_request_id(request),
            details=[ErrorDetail(field="cursor", message="cursor is invalid.")],
            status_code=400,
        )


@router.get("/tickets/public/{ticket_number}", response_model=PublicTicketResponse)
def get_public_ticket(
    ticket_number: str,
    request: Request,
) -> PublicTicketResponse | JSONResponse:
    """Unauthenticated citizen-safe public report detail by ticket number."""
    limited = enforce_rate_limit(
        request,
        "public-ticket-browsing",
        message="Too many public ticket requests. Please wait before trying again.",
    )
    if limited is not None:
        return limited

    ticket = ticket_service.get_public_ticket(ticket_number)
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
    principal: StaffDep,
) -> TicketResponse | JSONResponse:
    """Staff ticket detail (issue #72). Auth is checked before any ticket lookup
    so unauthorized callers never learn whether an ID exists.
    """
    ticket = ticket_service.get_ticket(ticket_id, staff_principal=principal)
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
    principal: StaffDep,
) -> TicketResponse | JSONResponse:
    try:
        verified_payload = payload.model_copy(update={"updated_by": principal.staff_id})
        return ticket_service.update_ticket_status(
            ticket_id,
            verified_payload,
            staff_principal=principal,
        )
    except TicketNotFoundError:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    except (InvalidStatusTransitionError, MissingDepartmentAssignmentError) as exc:
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
    principal: StaffDep,
) -> TicketResponse | JSONResponse:
    try:
        verified_payload = payload.model_copy(update={"category_reviewed_by": principal.staff_id})
        return ticket_service.review_ticket_category(
            ticket_id,
            verified_payload,
            staff_principal=principal,
        )
    except TicketNotFoundError:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    except StaffScopeForbiddenError:
        return build_error_response(
            code="FORBIDDEN",
            message="You do not have permission to assign the department for this category.",
            request_id=get_request_id(request),
            status_code=403,
        )


@router.patch("/tickets/{ticket_id}/public", response_model=TicketResponse)
def update_ticket_public_content(
    ticket_id: str,
    payload: UpdateTicketPublicContentRequest,
    request: Request,
    principal: StaffDep,
) -> TicketResponse | JSONResponse:
    """Staff-approved public projection, including optional public photo approval."""
    try:
        verified_payload = payload.model_copy(update={"updated_by": principal.staff_id})
        return ticket_service.update_ticket_public_content(
            ticket_id,
            verified_payload,
            staff_principal=principal,
        )
    except TicketNotFoundError:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    except PublicContentUpdateError as exc:
        return build_error_response(
            code="VALIDATION_ERROR",
            message=str(exc),
            request_id=get_request_id(request),
            status_code=400,
        )


@router.patch("/tickets/{ticket_id}/department", response_model=TicketResponse)
def assign_ticket_department(
    ticket_id: str,
    payload: AssignTicketDepartmentRequest,
    request: Request,
    principal: StaffActorDep,
) -> TicketResponse | JSONResponse:
    """Staff department assignment (issue #141). Auth via ``StaffActorDep`` (#72)."""
    try:
        verified_payload = payload.model_copy(update={"updated_by": principal.staff_id})
        return ticket_service.assign_ticket_department(
            ticket_id,
            verified_payload,
            staff_principal=principal,
        )
    except TicketNotFoundError:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    except StaffScopeForbiddenError:
        return build_error_response(
            code="FORBIDDEN",
            message="You do not have permission to assign this department.",
            request_id=get_request_id(request),
            status_code=403,
        )


@router.post("/tickets/merge", response_model=TicketResponse)
def merge_duplicate_tickets(
    payload: MergeDuplicateTicketsRequest,
    request: Request,
    principal: StaffDep,
) -> TicketResponse | JSONResponse:
    try:
        verified_payload = payload.model_copy(update={"merged_by": principal.staff_id})
        return ticket_service.merge_duplicate_tickets(
            verified_payload,
            staff_principal=principal,
        )
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
