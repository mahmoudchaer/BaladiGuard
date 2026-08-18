"""Staff resolution-feedback review API (issues #248 / #261)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.errors import build_error_response, get_request_id
from app.core.staff_auth import MunicipalStaffDep as StaffDep
from app.schemas.resolution_feedback import (
    ResolutionReviewQueueResponse,
    ReviewResolutionFeedbackRequest,
    StaffResolutionFeedbackResponse,
)
from app.services.resolution_feedback.service import (
    ResolutionFeedbackError,
    resolution_feedback_service,
)

router = APIRouter(prefix="/v1", tags=["resolution-feedback"])


def _error(request: Request, exc: ResolutionFeedbackError) -> JSONResponse:
    return build_error_response(
        code=exc.code,
        message=exc.message,
        request_id=get_request_id(request),
        status_code=exc.status_code,
    )


@router.get(
    "/tickets/{ticket_id}/resolution-feedback",
    response_model=StaffResolutionFeedbackResponse,
)
def get_ticket_resolution_feedback(
    ticket_id: str,
    request: Request,
    principal: StaffDep,
) -> StaffResolutionFeedbackResponse | JSONResponse:
    try:
        return resolution_feedback_service.staff_view(ticket_id, principal=principal)
    except ResolutionFeedbackError as exc:
        return _error(request, exc)


@router.post(
    "/tickets/{ticket_id}/resolution-feedback/review",
    response_model=StaffResolutionFeedbackResponse,
)
def review_ticket_resolution_feedback(
    ticket_id: str,
    payload: ReviewResolutionFeedbackRequest,
    request: Request,
    principal: StaffDep,
) -> StaffResolutionFeedbackResponse | JSONResponse:
    try:
        return resolution_feedback_service.review(ticket_id, payload, principal=principal)
    except ResolutionFeedbackError as exc:
        return _error(request, exc)


@router.get("/resolution-reviews", response_model=ResolutionReviewQueueResponse)
def list_resolution_reviews(
    request: Request, principal: StaffDep
) -> ResolutionReviewQueueResponse | JSONResponse:
    try:
        return resolution_feedback_service.list_review_queue(principal=principal)
    except ResolutionFeedbackError as exc:
        return _error(request, exc)
