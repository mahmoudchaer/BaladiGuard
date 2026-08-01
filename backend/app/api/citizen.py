"""Citizen profile endpoints (issue #169)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.citizen_auth import CitizenDep
from app.core.errors import build_error_response, get_request_id
from app.schemas.citizen import CitizenProfileResponse, CitizenProfileUpdateRequest
from app.services.citizens.service import CitizenServiceError, citizen_service

router = APIRouter(prefix="/v1/citizen", tags=["citizen"])


def _service_error_response(request: Request, exc: CitizenServiceError) -> JSONResponse:
    return build_error_response(
        code=exc.code,
        message=exc.message,
        request_id=get_request_id(request),
        status_code=exc.status_code,
    )


@router.get("/me", response_model=CitizenProfileResponse)
def get_citizen_me(
    request: Request,
    principal: CitizenDep,
) -> CitizenProfileResponse | JSONResponse:
    try:
        return citizen_service.get_profile(principal.user_id)
    except CitizenServiceError as exc:
        return _service_error_response(request, exc)


@router.patch("/me", response_model=CitizenProfileResponse)
def patch_citizen_me(
    payload: CitizenProfileUpdateRequest,
    request: Request,
    principal: CitizenDep,
) -> CitizenProfileResponse | JSONResponse:
    try:
        return citizen_service.update_profile(principal.user_id, payload)
    except CitizenServiceError as exc:
        response = _service_error_response(request, exc)
        if exc.status_code == 401:
            response.headers["WWW-Authenticate"] = "Bearer"
        return response
