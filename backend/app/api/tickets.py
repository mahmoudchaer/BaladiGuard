import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import ContributionReadyCitizenDep, StaffActorDep
from app.core.citizen_auth import unauthorized
from app.core.errors import ErrorDetail, build_error_response, get_request_id
from app.core.rate_limit import enforce_rate_limit
from app.core.staff_auth import StaffDep
from app.database.store_factory import get_citizen_store
from app.schemas.image_redaction import (
    ImageRedactionDecisionRequest,
    ImageRedactionReviewResponse,
    ReprocessImageResponse,
)
from app.schemas.staff_assistant import StaffAssistantQuery, StaffAssistantResponse
from app.schemas.staff_comment import (
    ActivityTimelineResponse,
    CreateStaffCommentRequest,
    StaffCommentResponse,
)
from app.schemas.staff_ticket_collection import (
    TicketAggregatesResponse,
    TicketListPageResponse,
    TicketMapViewportResponse,
)
from app.schemas.ticket import SubmitTicketRequest, SubmitTicketResponse
from app.schemas.ticket_ai_update import AssignTicketDepartmentRequest, ReviewTicketCategoryRequest
from app.schemas.ticket_duplicates import (
    DUPLICATE_CANDIDATE_DEFAULT_LIMIT,
    DUPLICATE_CANDIDATE_MAX_LIMIT,
    DuplicateCandidatePageResponse,
    DuplicateComparisonResponse,
)
from app.schemas.ticket_merge import MergeDuplicateTicketsRequest
from app.schemas.ticket_response import (
    CitizenTicketResponse,
    PublicTicketListResponse,
    PublicTicketMapViewportResponse,
    PublicTicketResponse,
    TicketResponse,
    UpdateTicketPublicContentRequest,
    UpdateTicketStatusRequest,
)
from app.schemas.ticket_status import TicketStatus
from app.schemas.workforce import AssignWorkforceRequest
from app.services.ai_job_queue import ai_job_queue
from app.services.citizens.service import snapshot_contact_for_ticket
from app.services.complaints.status_workflow import (
    InvalidStatusTransitionError,
    MissingDepartmentAssignmentError,
)
from app.services.complaints.ticket_list_filters import parse_ticket_list_filters
from app.services.complaints.ticket_service import (
    PUBLIC_MAP_DEFAULT_LIMIT,
    PUBLIC_MAP_MAX_LIMIT,
    STAFF_MAP_DEFAULT_LIMIT,
    STAFF_MAP_MAX_LIMIT,
    STAFF_TICKET_DEFAULT_LIMIT,
    STAFF_TICKET_MAX_LIMIT,
    DuplicateMergeError,
    PublicContentUpdateError,
    StaffScopeForbiddenError,
    TicketNotFoundError,
    TicketSubmissionInProgressError,
    ticket_service,
)
from app.services.redaction.queue import image_redaction_queue
from app.services.redaction.review import (
    ImageRedactionReviewConflictError,
    ImageRedactionReviewError,
)
from app.services.staff.assistant import staff_assistant_service
from app.services.staff.comments import StaffCommentError, staff_comment_service
from app.services.workforce.service import WorkforceError
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


def _staff_comment_error(request: Request, exc: StaffCommentError) -> JSONResponse:
    return build_error_response(
        code=exc.code,
        message=exc.message,
        request_id=get_request_id(request),
        status_code=exc.status_code,
    )


@router.post("/tickets/{ticket_id}/comments", response_model=StaffCommentResponse, status_code=201)
def create_staff_comment(
    ticket_id: str, payload: CreateStaffCommentRequest, request: Request, principal: StaffDep
) -> StaffCommentResponse | JSONResponse:
    try:
        return staff_comment_service.create(ticket_id, payload, principal=principal)
    except StaffCommentError as exc:
        return _staff_comment_error(request, exc)


@router.get("/tickets/{ticket_id}/comments", response_model=list[StaffCommentResponse])
def list_staff_comments(
    ticket_id: str, request: Request, principal: StaffDep
) -> list[StaffCommentResponse] | JSONResponse:
    try:
        return staff_comment_service.list(ticket_id, principal=principal)
    except StaffCommentError as exc:
        return _staff_comment_error(request, exc)


@router.get("/tickets/{ticket_id}/activity", response_model=ActivityTimelineResponse)
def get_ticket_activity(
    ticket_id: str,
    request: Request,
    principal: StaffDep,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> ActivityTimelineResponse | JSONResponse:
    try:
        return staff_comment_service.timeline(
            ticket_id, principal=principal, limit=limit, cursor=cursor
        )
    except ValueError:
        return build_error_response(
            code="VALIDATION_ERROR",
            message="The activity cursor is invalid.",
            request_id=get_request_id(request),
            status_code=400,
        )
    except StaffCommentError as exc:
        return _staff_comment_error(request, exc)


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
    try:
        image_redaction_queue.enqueue(response.ticket_id)
    except Exception as exc:
        logger.warning(
            "Image redaction queue write deferred ticket_id=%s error=%s",
            response.ticket_id,
            type(exc).__name__,
        )
    return response


@router.post(
    "/tickets/{ticket_id}/image-redaction/reprocess",
    response_model=ReprocessImageResponse,
    status_code=202,
)
def reprocess_ticket_image(
    ticket_id: str,
    request: Request,
    principal: StaffDep,
) -> ReprocessImageResponse | JSONResponse:
    try:
        generation = ticket_service.request_image_reprocessing(ticket_id, staff_principal=principal)
    except TicketNotFoundError:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    except ImageRedactionReviewConflictError as exc:
        return _redaction_review_error(request, exc)
    image_redaction_queue.enqueue(ticket_id, generation)
    return ReprocessImageResponse(ticketId=ticket_id, generation=generation)


def _redaction_review_error(request: Request, exc: ImageRedactionReviewError) -> JSONResponse:
    status = 409 if isinstance(exc, ImageRedactionReviewConflictError) else 400
    return build_error_response(
        code=exc.code,
        message=str(exc),
        request_id=get_request_id(request),
        status_code=status,
    )


@router.get(
    "/tickets/{ticket_id}/image-redaction/review",
    response_model=ImageRedactionReviewResponse,
)
def get_image_redaction_review(
    ticket_id: str,
    request: Request,
    principal: StaffDep,
) -> ImageRedactionReviewResponse | JSONResponse:
    try:
        return ticket_service.get_image_redaction_review(ticket_id, staff_principal=principal)
    except TicketNotFoundError:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )


@router.post(
    "/tickets/{ticket_id}/image-redaction/approve",
    response_model=ImageRedactionReviewResponse,
)
def approve_image_redaction(
    ticket_id: str,
    payload: ImageRedactionDecisionRequest,
    request: Request,
    principal: StaffDep,
) -> ImageRedactionReviewResponse | JSONResponse:
    try:
        return ticket_service.approve_image_redaction(ticket_id, payload, staff_principal=principal)
    except TicketNotFoundError:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    except ImageRedactionReviewError as exc:
        return _redaction_review_error(request, exc)


@router.post(
    "/tickets/{ticket_id}/image-redaction/reject",
    response_model=ImageRedactionReviewResponse,
)
def reject_image_redaction(
    ticket_id: str,
    payload: ImageRedactionDecisionRequest,
    request: Request,
    principal: StaffDep,
) -> ImageRedactionReviewResponse | JSONResponse:
    try:
        return ticket_service.reject_image_redaction(ticket_id, payload, staff_principal=principal)
    except TicketNotFoundError:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    except ImageRedactionReviewError as exc:
        return _redaction_review_error(request, exc)


@router.post(
    "/tickets/{ticket_id}/image-redaction/manual-regions",
    response_model=ImageRedactionReviewResponse,
)
def apply_manual_image_redaction(
    ticket_id: str,
    payload: ImageRedactionDecisionRequest,
    request: Request,
    principal: StaffDep,
) -> ImageRedactionReviewResponse | JSONResponse:
    try:
        return ticket_service.apply_manual_image_redaction(
            ticket_id, payload, staff_principal=principal
        )
    except TicketNotFoundError:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    except ImageRedactionReviewError as exc:
        return _redaction_review_error(request, exc)


@router.get("/tickets", response_model=TicketListPageResponse)
def list_tickets(
    principal: StaffDep,
    request: Request,
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    urgency: str | None = Query(default=None),
    department_id: str | None = Query(default=None, alias="departmentId"),
    sla_state: str | None = Query(default=None, alias="slaState"),
    assignment_state: str | None = Query(default=None, alias="assignmentState"),
    worker_id: str | None = Query(default=None, alias="workerId"),
    team_id: str | None = Query(default=None, alias="teamId"),
    workforce_unassigned: bool = Query(default=False, alias="workforceUnassigned"),
    q: str | None = Query(default=None),
    open_only: bool = Query(default=False, alias="openOnly"),
    limit: int = Query(default=STAFF_TICKET_DEFAULT_LIMIT, ge=1, le=STAFF_TICKET_MAX_LIMIT),
    cursor: str | None = Query(default=None),
) -> TicketListPageResponse | JSONResponse:
    """Staff dashboard ticket list with cursor pagination (issue #267)."""
    filters, errors = parse_ticket_list_filters(
        status=status,
        category=category,
        urgency=urgency,
        department_id=department_id,
        sla_state=sla_state,
        assignment_state=assignment_state,
        worker_id=worker_id,
        team_id=team_id,
        workforce_unassigned=workforce_unassigned,
        q=q,
        open_only=open_only,
    )
    if errors:
        return build_error_response(
            code="VALIDATION_ERROR",
            message="The request contains invalid fields.",
            request_id=get_request_id(request),
            details=[ErrorDetail(field=error.field, message=error.message) for error in errors],
            status_code=400,
        )
    try:
        return ticket_service.list_tickets_page(
            filters,
            staff_principal=principal,
            limit=limit,
            cursor=cursor,
        )
    except ValueError:
        return build_error_response(
            code="VALIDATION_ERROR",
            message="The ticket list cursor is invalid.",
            request_id=get_request_id(request),
            details=[ErrorDetail(field="cursor", message="cursor is invalid.")],
            status_code=400,
        )


@router.get("/tickets/map", response_model=TicketMapViewportResponse)
def map_tickets_viewport(
    principal: StaffDep,
    request: Request,
    north: float = Query(...),
    south: float = Query(...),
    east: float = Query(...),
    west: float = Query(...),
    zoom: float = Query(...),
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    urgency: str | None = Query(default=None),
    department_id: str | None = Query(default=None, alias="departmentId"),
    sla_state: str | None = Query(default=None, alias="slaState"),
    limit: int = Query(default=STAFF_MAP_DEFAULT_LIMIT, ge=1, le=STAFF_MAP_MAX_LIMIT),
) -> TicketMapViewportResponse | JSONResponse:
    """Staff map viewport with markers or grid clusters (issue #267)."""
    if south > north:
        return build_error_response(
            code="VALIDATION_ERROR",
            message="The request contains invalid fields.",
            request_id=get_request_id(request),
            details=[ErrorDetail(field="south", message="south must be <= north.")],
            status_code=400,
        )
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
    return ticket_service.map_viewport(
        staff_principal=principal,
        north=north,
        south=south,
        east=east,
        west=west,
        zoom=zoom,
        filters=filters,
        limit=limit,
    )


@router.get("/tickets/aggregates", response_model=TicketAggregatesResponse)
def ticket_aggregates(
    principal: StaffDep,
) -> TicketAggregatesResponse:
    """Staff dashboard attention counts (issue #267)."""
    return ticket_service.ticket_aggregates(principal)


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
    q: str | None = Query(default=None, min_length=1, max_length=80),
    status: TicketStatus | None = None,
    category: str | None = Query(default=None, min_length=1, max_length=80),
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
        return ticket_service.list_public_tickets(
            limit=limit,
            cursor=cursor,
            q=q,
            status=status,
            category=category,
        )
    except ValueError:
        return build_error_response(
            code="VALIDATION_ERROR",
            message="The public report cursor is invalid.",
            request_id=get_request_id(request),
            details=[ErrorDetail(field="cursor", message="cursor is invalid.")],
            status_code=400,
        )


@router.get("/tickets/public/map", response_model=PublicTicketMapViewportResponse)
def public_map_tickets_viewport(
    request: Request,
    north: float = Query(..., ge=-90, le=90),
    south: float = Query(..., ge=-90, le=90),
    east: float = Query(..., ge=-180, le=180),
    west: float = Query(..., ge=-180, le=180),
    zoom: float = Query(..., ge=0, le=22),
    limit: int = Query(default=PUBLIC_MAP_DEFAULT_LIMIT, ge=1, le=PUBLIC_MAP_MAX_LIMIT),
) -> PublicTicketMapViewportResponse | JSONResponse:
    """Bounded public markers/clusters for only the requested map viewport."""
    limited = enforce_rate_limit(
        request,
        "public-ticket-browsing",
        message="Too many public ticket requests. Please wait before trying again.",
    )
    if limited is not None:
        return limited
    if south > north:
        return build_error_response(
            code="VALIDATION_ERROR",
            message="The request contains invalid fields.",
            request_id=get_request_id(request),
            details=[ErrorDetail(field="south", message="south must be <= north.")],
            status_code=400,
        )
    return ticket_service.public_map_viewport(
        north=north,
        south=south,
        east=east,
        west=west,
        zoom=zoom,
        limit=limit,
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


@router.get(
    "/tickets/{ticket_id}/duplicate-candidates",
    response_model=DuplicateCandidatePageResponse,
)
def list_duplicate_candidates(
    ticket_id: str,
    request: Request,
    principal: StaffDep,
    q: str | None = Query(default=None),
    limit: int = Query(
        default=DUPLICATE_CANDIDATE_DEFAULT_LIMIT,
        ge=1,
        le=DUPLICATE_CANDIDATE_MAX_LIMIT,
    ),
    cursor: str | None = Query(default=None),
) -> DuplicateCandidatePageResponse | JSONResponse:
    """Mergeable duplicate candidates for one ticket, cursor-paginated (issue #269)."""
    try:
        return ticket_service.list_duplicate_candidates(
            ticket_id,
            staff_principal=principal,
            q=q,
            limit=limit,
            cursor=cursor,
        )
    except TicketNotFoundError:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    except ValueError:
        return build_error_response(
            code="VALIDATION_ERROR",
            message="The duplicate candidate cursor is invalid.",
            request_id=get_request_id(request),
            details=[ErrorDetail(field="cursor", message="cursor is invalid.")],
            status_code=400,
        )


@router.get(
    "/tickets/{ticket_id}/duplicate-comparison/{candidate_ticket_id}",
    response_model=DuplicateComparisonResponse,
)
def get_duplicate_comparison(
    ticket_id: str,
    candidate_ticket_id: str,
    request: Request,
    principal: StaffDep,
) -> DuplicateComparisonResponse | JSONResponse:
    """Bounded side-by-side comparison projection for the merge review (issue #269)."""
    try:
        return ticket_service.get_duplicate_comparison(
            ticket_id,
            candidate_ticket_id,
            staff_principal=principal,
        )
    except TicketNotFoundError:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )


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


@router.post("/tickets/{ticket_id}/workforce-assignment", response_model=TicketResponse)
def assign_ticket_workforce(
    ticket_id: str,
    payload: AssignWorkforceRequest,
    request: Request,
    principal: StaffActorDep,
) -> TicketResponse | JSONResponse:
    """Assign a municipality worker XOR team to a ticket (issue #245)."""
    try:
        return ticket_service.assign_ticket_workforce(
            ticket_id,
            payload,
            staff_principal=principal,
        )
    except TicketNotFoundError:
        return build_error_response(
            code="TICKET_NOT_FOUND",
            message="Ticket was not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    except WorkforceError as exc:
        return build_error_response(
            code=exc.code,
            message=exc.message,
            request_id=get_request_id(request),
            status_code=exc.status_code,
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
