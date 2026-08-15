"""Citizen profile and OTP authentication endpoints (issues #169 / #170)."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.citizen_auth import (
    CITIZEN_SESSION_TTL_SECONDS,
    CITIZEN_WEB_SESSION_COOKIE,
    CitizenDep,
    OptionalCitizenDep,
)
from app.core.errors import build_error_response, get_request_id
from app.core.metrics import emit_metric
from app.core.rate_limit import enforce_rate_limit
from app.schemas.citizen import (
    CitizenDataExportResponse,
    CitizenDeleteResponse,
    CitizenProfileResponse,
    CitizenProfileUpdateRequest,
    CitizenTicketHistoryResponse,
)
from app.schemas.citizen_auth import (
    CitizenOtpRequest,
    CitizenOtpRequestResponse,
    CitizenOtpVerifyRequest,
    CitizenOtpVerifyResponse,
)
from app.schemas.resolution_feedback import (
    CitizenResolutionFeedbackResponse,
    SubmitResolutionFeedbackRequest,
)
from app.services.citizens.otp_delivery import deliver_citizen_otp
from app.services.citizens.service import (
    CHANGE_PHONE_PURPOSE,
    CITIZEN_TICKET_HISTORY_DEFAULT_LIMIT,
    CITIZEN_TICKET_HISTORY_MAX_LIMIT,
    GENERIC_OTP_MESSAGE,
    LOGIN_OR_SIGNUP_PURPOSE,
    CitizenServiceError,
    citizen_service,
)
from app.utils.phone import PhoneNormalizationError, normalize_phone

router = APIRouter(prefix="/v1/citizen", tags=["citizen"])


def _service_error_response(request: Request, exc: CitizenServiceError) -> JSONResponse:
    if exc.status_code == 401:
        emit_metric("AuthFailures", dimensions={"kind": "citizen", "code": exc.code})
    response = build_error_response(
        code=exc.code,
        message=exc.message,
        request_id=get_request_id(request),
        status_code=exc.status_code,
    )
    if exc.status_code == 401:
        response.headers["WWW-Authenticate"] = "Bearer"
    if exc.status_code == 429:
        response.headers.setdefault("Retry-After", "60")
    return response


def _phone_rate_identity(phone: str, region: str | None) -> str | None:
    try:
        return f"phone:{normalize_phone(phone, region)}"
    except PhoneNormalizationError:
        return None


@router.post(
    "/auth/otp/request",
    response_model=CitizenOtpRequestResponse,
    status_code=202,
)
def request_citizen_otp(
    payload: CitizenOtpRequest,
    request: Request,
    principal: OptionalCitizenDep,
) -> CitizenOtpRequestResponse | JSONResponse:
    settings = get_settings()
    phone_identity = _phone_rate_identity(payload.phone, payload.region)
    device_id = (request.headers.get("X-Device-Id") or "").strip() or None

    limited = enforce_rate_limit(
        request,
        "citizen-otp-request",
        settings=settings,
        message="Too many verification requests. Please wait before trying again.",
        extra_identity=phone_identity,
    )
    if limited is not None:
        return limited
    if device_id:
        limited = enforce_rate_limit(
            request,
            "citizen-otp-request",
            settings=settings,
            message="Too many verification requests. Please wait before trying again.",
            extra_identity=f"device:{device_id}",
        )
        if limited is not None:
            return limited

    if payload.purpose == CHANGE_PHONE_PURPOSE and principal is None:
        response = build_error_response(
            code="UNAUTHORIZED",
            message="Citizen authentication required.",
            request_id=get_request_id(request),
            status_code=401,
        )
        response.headers["WWW-Authenticate"] = "Bearer"
        return response

    if payload.purpose == LOGIN_OR_SIGNUP_PURPOSE:
        auth_user_id = None
    else:
        auth_user_id = principal.user_id if principal is not None else None

    try:
        challenge_id, expires_in, code = citizen_service.request_otp(
            phone=payload.phone,
            region=payload.region,
            purpose=payload.purpose,
            authenticated_user_id=auth_user_id,
        )
    except CitizenServiceError as exc:
        # Keep LOGIN_OR_SIGNUP failures account-neutral where possible.
        if payload.purpose == LOGIN_OR_SIGNUP_PURPOSE and exc.code == "VALIDATION_ERROR":
            return _service_error_response(request, exc)
        return _service_error_response(request, exc)

    # HTTP response stays code-free; delivery is side-effect only.
    # If real delivery raises, invalidate the unused challenge so it cannot linger.
    try:
        deliver_citizen_otp(
            phone=payload.phone,
            region=payload.region,
            code=code,
            settings=settings,
        )
    except Exception:
        citizen_service.invalidate_otp_challenge(challenge_id)
        raise

    return CitizenOtpRequestResponse(
        challengeId=challenge_id,
        expiresIn=expires_in,
        message=GENERIC_OTP_MESSAGE,
    )


WEB_SESSION_HEADER = "X-Citizen-Session-Mode"


def _use_secure_cookie() -> bool:
    return get_settings().app_env in {"staging", "production"}


@router.post(
    "/auth/otp/verify",
    response_model=CitizenOtpVerifyResponse,
)
def verify_citizen_otp(
    payload: CitizenOtpVerifyRequest,
    request: Request,
    principal: OptionalCitizenDep,
) -> CitizenOtpVerifyResponse | JSONResponse:
    settings = get_settings()
    device_id = (request.headers.get("X-Device-Id") or "").strip() or None
    limited = enforce_rate_limit(
        request,
        "citizen-otp-verify",
        settings=settings,
        message="Too many verification attempts. Please wait before trying again.",
        extra_identity=f"challenge:{payload.challenge_id}",
    )
    if limited is not None:
        return limited
    if device_id:
        limited = enforce_rate_limit(
            request,
            "citizen-otp-verify",
            settings=settings,
            message="Too many verification attempts. Please wait before trying again.",
            extra_identity=f"device:{device_id}",
        )
        if limited is not None:
            return limited

    try:
        verified = citizen_service.verify_otp(
            challenge_id=payload.challenge_id,
            code=payload.code,
            full_name=payload.full_name,
            authenticated_user_id=principal.user_id if principal is not None else None,
        )
        if request.headers.get(WEB_SESSION_HEADER, "").strip().lower() == "cookie":
            if verified.access_token is None:
                return verified
            browser_response = JSONResponse(
                content=verified.model_dump(
                    by_alias=True,
                    mode="json",
                    exclude={"access_token"},
                )
            )
            browser_response.set_cookie(
                key=CITIZEN_WEB_SESSION_COOKIE,
                value=verified.access_token,
                max_age=CITIZEN_SESSION_TTL_SECONDS,
                httponly=True,
                secure=_use_secure_cookie(),
                samesite="lax",
                path="/v1",
            )
            return browser_response
        return verified
    except CitizenServiceError as exc:
        return _service_error_response(request, exc)


@router.post("/auth/logout", status_code=204, response_class=Response)
def logout_citizen(principal: CitizenDep) -> Response:
    # CitizenDep already authenticated the presented session; revoke it best-effort.
    try:
        citizen_service.logout_session(principal.session_id)
    except CitizenServiceError:
        # Session disappeared between auth and revoke — treat as logged out.
        pass
    response = Response(status_code=204)
    response.delete_cookie(
        CITIZEN_WEB_SESSION_COOKIE,
        path="/v1",
        secure=_use_secure_cookie(),
        httponly=True,
        samesite="lax",
    )
    return response


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
        return _service_error_response(request, exc)


@router.get("/me/export", response_model=CitizenDataExportResponse)
def export_citizen_me(
    request: Request,
    principal: CitizenDep,
) -> CitizenDataExportResponse | JSONResponse:
    """Authenticated privacy export of profile + owned tickets (issue #190)."""
    try:
        return citizen_service.export_account(principal.user_id)
    except CitizenServiceError as exc:
        return _service_error_response(request, exc)


@router.get("/me/tickets", response_model=CitizenTicketHistoryResponse)
def list_citizen_ticket_history(
    request: Request,
    principal: CitizenDep,
    limit: int = Query(
        default=CITIZEN_TICKET_HISTORY_DEFAULT_LIMIT,
        ge=1,
        le=CITIZEN_TICKET_HISTORY_MAX_LIMIT,
    ),
    cursor: str | None = Query(default=None),
) -> CitizenTicketHistoryResponse | JSONResponse:
    """Authenticated citizen-owned ticket history (issue #174)."""
    try:
        return citizen_service.list_ticket_history(
            principal.user_id,
            limit=limit,
            cursor=cursor,
        )
    except CitizenServiceError as exc:
        return _service_error_response(request, exc)


@router.get(
    "/me/tickets/{tracking_code}/resolution-feedback",
    response_model=CitizenResolutionFeedbackResponse,
)
def get_citizen_resolution_feedback(
    tracking_code: str,
    request: Request,
    principal: CitizenDep,
) -> CitizenResolutionFeedbackResponse | JSONResponse:
    from app.services.resolution_feedback.service import (
        ResolutionFeedbackError,
        resolution_feedback_service,
    )

    try:
        return resolution_feedback_service.citizen_view(
            tracking_code, owner_user_id=principal.user_id
        )
    except ResolutionFeedbackError as exc:
        return build_error_response(
            code=exc.code,
            message=exc.message,
            request_id=get_request_id(request),
            status_code=exc.status_code,
        )


@router.post(
    "/me/tickets/{tracking_code}/resolution-feedback",
    response_model=CitizenResolutionFeedbackResponse,
)
def submit_citizen_resolution_feedback(
    tracking_code: str,
    payload: SubmitResolutionFeedbackRequest,
    request: Request,
    principal: CitizenDep,
) -> CitizenResolutionFeedbackResponse | JSONResponse:
    from app.services.resolution_feedback.service import (
        ResolutionFeedbackError,
        resolution_feedback_service,
    )

    try:
        return resolution_feedback_service.submit_citizen_feedback(
            tracking_code, payload, owner_user_id=principal.user_id
        )
    except ResolutionFeedbackError as exc:
        return build_error_response(
            code=exc.code,
            message=exc.message,
            request_id=get_request_id(request),
            status_code=exc.status_code,
        )


@router.post("/me/delete", response_model=CitizenDeleteResponse)
def delete_citizen_me(
    request: Request,
    principal: CitizenDep,
) -> CitizenDeleteResponse | JSONResponse:
    """Anonymize the authenticated citizen account (issue #190)."""
    try:
        return citizen_service.delete_account(principal.user_id)
    except CitizenServiceError as exc:
        return _service_error_response(request, exc)
