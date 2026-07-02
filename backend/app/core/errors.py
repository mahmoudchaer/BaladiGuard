from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: str = Field(alias="requestId")

    model_config = {"populate_by_name": True}


class ErrorResponse(BaseModel):
    error: ErrorBody


def create_request_id() -> str:
    return f"req_{uuid4().hex[:12]}"


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", create_request_id())


def build_error_response(
    *,
    code: str,
    message: str,
    request_id: str,
    details: list[ErrorDetail] | None = None,
    status_code: int = 400,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            details=details or [],
            requestId=request_id,
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(by_alias=True))


def format_validation_details(errors: list[dict[str, Any]]) -> list[ErrorDetail]:
    details: list[ErrorDetail] = []
    for error in errors:
        field_parts = [str(part) for part in error.get("loc", ()) if part not in {"body"}]
        field = ".".join(field_parts) or "body"
        details.append(ErrorDetail(field=field, message=error.get("msg", "Invalid value.")))
    return details


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return build_error_response(
        code="VALIDATION_ERROR",
        message="The request contains invalid fields.",
        request_id=get_request_id(request),
        details=format_validation_details(exc.errors()),
        status_code=400,
    )
