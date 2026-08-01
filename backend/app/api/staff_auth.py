"""Staff authentication and password-reset endpoints (issues #175 / #178)."""

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
from app.schemas.staff_password_reset import (
    StaffPasswordResetConfirmRequest,
    StaffPasswordResetConfirmResponse,
    StaffPasswordResetRequest,
    StaffPasswordResetRequestResponse,
)
from app.services.staff.password_reset import (
    StaffPasswordResetError,
    staff_password_reset_service,
)

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


@router.post(
    "/staff/password-reset/request",
    response_model=StaffPasswordResetRequestResponse,
)
def request_staff_password_reset(
    payload: StaffPasswordResetRequest,
    request: Request,
) -> StaffPasswordResetRequestResponse | JSONResponse:
    settings = get_settings()
    limited = enforce_rate_limit(
        request,
        "staff-password-reset-request",
        settings=settings,
        message="Too many password reset requests. Please wait before trying again.",
        extra_identity=f"username:{payload.username}",
    )
    if limited is not None:
        return limited

    # Never return challengeId — presence would leak whether the username exists.
    message, _challenge_id = staff_password_reset_service.request_reset(payload.username)
    return StaffPasswordResetRequestResponse(message=message)


@router.post(
    "/staff/password-reset/confirm",
    response_model=StaffPasswordResetConfirmResponse,
)
def confirm_staff_password_reset(
    payload: StaffPasswordResetConfirmRequest,
    request: Request,
) -> StaffPasswordResetConfirmResponse | JSONResponse:
    settings = get_settings()
    limited = enforce_rate_limit(
        request,
        "staff-password-reset-confirm",
        settings=settings,
        message="Too many password reset attempts. Please wait before trying again.",
        extra_identity=f"username:{payload.username}",
    )
    if limited is not None:
        return limited

    try:
        message = staff_password_reset_service.confirm_reset(
            username=payload.username,
            code=payload.code,
            new_password=payload.new_password,
        )
    except StaffPasswordResetError as exc:
        response = build_error_response(
            code=exc.code,
            message=exc.message,
            request_id=get_request_id(request),
            status_code=exc.status_code,
        )
        if exc.status_code == 429:
            response.headers.setdefault("Retry-After", "60")
        return response

    return StaffPasswordResetConfirmResponse(message=message)
