import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import app.config  # noqa: F401 - load .env before other app modules
from app.api.citizen import router as citizen_router
from app.api.health import router as health_router
from app.api.locations import router as locations_router
from app.api.staff_auth import router as staff_auth_router
from app.api.tickets import router as tickets_router
from app.api.uploads import router as uploads_router
from app.core.config_validation import validate_configuration
from app.core.errors import (
    build_error_response,
    create_request_id,
    get_request_id,
)
from app.core.errors import (
    validation_exception_handler as base_validation_exception_handler,
)
from app.core.logging import configure_logging
from app.core.metrics import emit_metric, normalize_path_group, timed_metric
from app.core.request_context import reset_request_id, set_request_id
from app.core.upload_abuse import reject_upload_abuse_early
from app.services.complaints.ticket_service import ticket_service

logger = logging.getLogger(__name__)

LOCAL_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:8082",
    "http://127.0.0.1:8082",
    "http://localhost:19006",
    "http://127.0.0.1:19006",
]


def _with_request_id_header(response: JSONResponse, request_id: str) -> JSONResponse:
    response.headers["X-Request-Id"] = request_id
    return response


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    logger.info("BaladiGuard API starting up.")
    config_result = validate_configuration()
    for issue in config_result.issues:
        log = logger.error if issue.severity == "error" else logger.warning
        log(
            "Configuration validation code=%s severity=%s message=%s",
            issue.code,
            issue.severity,
            issue.message,
        )
    if config_result.should_abort_startup:
        # Message intentionally omits secret values; details are already logged above.
        raise RuntimeError(
            "Configuration validation failed. "
            "Fix the reported config issues (including APP_ENV) and restart."
        )
    # Memory/local bootstrap for demo staff accounts (issue #175). DynamoDB uses
    # `make db-seed` / run_seed instead.
    from app.config import get_settings
    from app.services.staff.bootstrap import ensure_demo_staff_accounts

    settings = get_settings()
    if not settings.use_dynamodb:
        ensure_demo_staff_accounts(settings=settings)
    # A worker crash between the 201 response and the terminal AI status leaves
    # tickets stuck in "pending"; sweep them off the request path at startup.
    threading.Thread(
        target=ticket_service.recover_pending_ai_tickets,
        name="ai-pending-recovery",
        daemon=True,
    ).start()
    yield
    logger.info("BaladiGuard API shutting down.")


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    request_id = get_request_id(request)
    logger.warning(
        "Request validation failed method=%s path=%s request_id=%s errors=%s",
        request.method,
        request.url.path,
        request_id,
        len(exc.errors()),
    )
    response = await base_validation_exception_handler(request, exc)
    return _with_request_id_header(response, request_id)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = get_request_id(request)
    if exc.status_code >= 500:
        logger.error(
            "HTTP error method=%s path=%s status=%s request_id=%s detail=%s",
            request.method,
            request.url.path,
            exc.status_code,
            request_id,
            exc.detail,
        )
    elif exc.status_code >= 400:
        logger.info(
            "HTTP client error method=%s path=%s status=%s request_id=%s",
            request.method,
            request.url.path,
            exc.status_code,
            request_id,
        )

    if isinstance(exc.detail, dict) and "error" in exc.detail:
        response = JSONResponse(status_code=exc.status_code, content=exc.detail)
    else:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        response = build_error_response(
            code="HTTP_ERROR",
            message=message,
            request_id=request_id,
            status_code=exc.status_code,
        )
    # Preserve auth challenge headers (e.g. WWW-Authenticate on 401).
    if exc.headers:
        for header_name, header_value in exc.headers.items():
            response.headers[header_name] = header_value
    return _with_request_id_header(response, request_id)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = get_request_id(request)
    logger.exception(
        "Unhandled request error method=%s path=%s request_id=%s (%s)",
        request.method,
        request.url.path,
        request_id,
        type(exc).__name__,
    )
    response = build_error_response(
        code="INTERNAL_ERROR",
        message="An unexpected server error occurred.",
        request_id=request_id,
        status_code=500,
    )
    return _with_request_id_header(response, request_id)


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="BaladiGuard API",
        version="0.1.0",
        description="BaladiGuard civic reporting backend API.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request.state.request_id = create_request_id()
        context_token = set_request_id(request.state.request_id)
        started_at = time.perf_counter()
        path_group = normalize_path_group(request.url.path)
        try:
            # Upload abuse checks must run before call_next so FastAPI never spools
            # multipart bodies for over-limit / over-quota report-photo requests.
            early_upload_rejection = reject_upload_abuse_early(request)
            if early_upload_rejection is not None:
                _record_http_metrics(
                    method=request.method,
                    path_group=path_group,
                    status_code=early_upload_rejection.status_code,
                    started_at=started_at,
                )
                return _with_request_id_header(early_upload_rejection, request.state.request_id)
            try:
                response = await call_next(request)
            except Exception:
                # BaseHTTPMiddleware can re-raise past exception handlers; still return
                # a correlated 500 so clients get X-Request-Id on both body and header.
                logger.exception(
                    "Unhandled request error method=%s path=%s request_id=%s",
                    request.method,
                    request.url.path,
                    request.state.request_id,
                )
                response = build_error_response(
                    code="INTERNAL_ERROR",
                    message="An unexpected server error occurred.",
                    request_id=request.state.request_id,
                    status_code=500,
                )
                _record_http_metrics(
                    method=request.method,
                    path_group=path_group,
                    status_code=500,
                    started_at=started_at,
                )
                return _with_request_id_header(response, request.state.request_id)
            response.headers["X-Request-Id"] = request.state.request_id
            if response.status_code >= 500:
                logger.error(
                    "Request failed method=%s path=%s status=%s request_id=%s",
                    request.method,
                    request.url.path,
                    response.status_code,
                    request.state.request_id,
                )
            _record_http_metrics(
                method=request.method,
                path_group=path_group,
                status_code=response.status_code,
                started_at=started_at,
            )
            return response
        finally:
            reset_request_id(context_token)

    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(health_router)
    app.include_router(staff_auth_router)
    app.include_router(citizen_router)
    app.include_router(tickets_router)
    app.include_router(locations_router)
    app.include_router(uploads_router)

    return app


def _record_http_metrics(
    *,
    method: str,
    path_group: str,
    status_code: int,
    started_at: float,
) -> None:
    dims = {
        "method": method.upper(),
        "path": path_group,
        "status": str(status_code),
        "status_class": f"{status_code // 100}xx",
    }
    emit_metric("HttpRequests", dimensions=dims)
    timed_metric("HttpRequestDuration", dimensions=dims, started_at=started_at)
    if status_code >= 500:
        emit_metric("Http5xx", dimensions=dims)


app = create_app()
