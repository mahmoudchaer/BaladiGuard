"""Staff authentication endpoints (issue #72)."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.errors import build_error_response, get_request_id
from app.core.staff_auth import (
    StaffAuthError,
    authenticate_staff_credentials,
    issue_staff_access_token,
)
from app.schemas.staff_auth import StaffLoginRequest, StaffLoginResponse

router = APIRouter(prefix="/v1", tags=["staff-auth"])


@router.post("/staff/login", response_model=StaffLoginResponse)
def staff_login(
    payload: StaffLoginRequest,
    request: Request,
) -> StaffLoginResponse | JSONResponse:
    settings = get_settings()
    try:
        principal = authenticate_staff_credentials(payload.username, payload.password, settings=settings)
    except StaffAuthError:
        return build_error_response(
            code="UNAUTHORIZED",
            message="Invalid staff username or password.",
            request_id=get_request_id(request),
            status_code=401,
        )

    token = issue_staff_access_token(principal.username, settings=settings)
    return StaffLoginResponse(
        accessToken=token,
        tokenType="Bearer",
        username=principal.username,
        expiresIn=settings.staff_token_ttl_seconds,
    )
