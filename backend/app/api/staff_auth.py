"""Staff authentication endpoints (issue #175)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.config import get_settings
from app.core.errors import build_error_response, get_request_id
from app.core.rate_limit import enforce_rate_limit
from app.core.staff_auth import (
    StaffAuthError,
    StaffDep,
    authenticate_staff_credentials,
    issue_staff_access_token,
    revoke_staff_sessions,
    unauthorized,
)
from app.schemas.staff_auth import StaffLoginRequest, StaffLoginResponse

router = APIRouter(prefix="/v1", tags=["staff-auth"])


@router.post("/staff/login", response_model=StaffLoginResponse)
def staff_login(
    payload: StaffLoginRequest,
    request: Request,
) -> StaffLoginResponse | JSONResponse:
    settings = get_settings()
    limited = enforce_rate_limit(
        request,
        "staff-login",
        settings=settings,
        message="Too many login attempts. Please wait before trying again.",
    )
    if limited is not None:
        return limited

    try:
        principal = authenticate_staff_credentials(
            payload.username,
            payload.password,
            settings=settings,
        )
    except StaffAuthError:
        return build_error_response(
            code="UNAUTHORIZED",
            message="Invalid staff username or password.",
            request_id=get_request_id(request),
            status_code=401,
        )

    token = issue_staff_access_token(principal, settings=settings)
    return StaffLoginResponse(
        accessToken=token,
        tokenType="Bearer",
        staffId=principal.staff_id,
        username=principal.username,
        name=principal.name,
        role=principal.role,
        municipalityId=principal.municipality_id,
        departmentIds=principal.department_ids,
        expiresIn=settings.staff_token_ttl_seconds,
    )


@router.post("/staff/logout")
def staff_logout(
    request: Request,
    principal: StaffDep,
) -> Response:
    try:
        revoke_staff_sessions(principal.staff_id)
    except StaffAuthError:
        raise unauthorized(request) from None
    return Response(status_code=204)
