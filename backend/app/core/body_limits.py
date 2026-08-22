"""Request size and header bounds enforced before route handlers (issue #316).

Upload paths keep the existing multipart ceiling in ``upload_abuse``. The
WhatsApp webhook keeps ``WHATSAPP_MAX_WEBHOOK_BYTES``. Every other write
gets a JSON/body ceiling so Starlette never buffers an unbounded payload.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import Message, Receive

from app.core.errors import build_error_response, get_request_id
from app.core.upload_abuse import is_report_photo_upload, is_work_order_evidence_upload

WHATSAPP_WEBHOOK_PATH = "/v1/whatsapp/webhook"
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class RequestBodyTooLarge(Exception):
    """Raised when a streamed request body exceeds the configured ceiling."""


def is_whatsapp_webhook(request: Request) -> bool:
    path = request.url.path.rstrip("/") or "/"
    return request.method == "POST" and path == WHATSAPP_WEBHOOK_PATH


def should_limit_json_body(request: Request) -> bool:
    if request.method not in WRITE_METHODS:
        return False
    if is_report_photo_upload(request) or is_work_order_evidence_upload(request):
        return False
    return True


def max_body_bytes_for_request(
    request: Request, *, json_max_bytes: int, webhook_max_bytes: int
) -> int:
    if is_whatsapp_webhook(request):
        return webhook_max_bytes
    return json_max_bytes


def _invalid_content_length(request: Request) -> JSONResponse:
    return build_error_response(
        code="VALIDATION_ERROR",
        message="Content-Length must be a valid non-negative integer.",
        request_id=get_request_id(request),
        status_code=400,
    )


def reject_oversized_headers(request: Request, *, max_header_bytes: int) -> JSONResponse | None:
    total = 0
    for name, value in request.headers.items():
        total += len(name) + len(value)
        if total > max_header_bytes:
            return build_error_response(
                code="HEADERS_TOO_LARGE",
                message="Request headers exceed the allowed size.",
                request_id=get_request_id(request),
                status_code=431,
            )
    return None


def reject_oversized_body(
    request: Request,
    *,
    max_bytes: int,
) -> JSONResponse | None:
    """Reject when Content-Length is present and over the ceiling."""
    if not should_limit_json_body(request):
        return None
    content_length = request.headers.get("content-length")
    if content_length is None or not content_length.strip():
        return None
    try:
        size = int(content_length.strip())
    except ValueError:
        return _invalid_content_length(request)
    if size < 0:
        return _invalid_content_length(request)
    if size > max_bytes:
        return build_error_response(
            code="PAYLOAD_TOO_LARGE",
            message="Request body exceeds the allowed size.",
            request_id=get_request_id(request),
            status_code=413,
        )
    return None


def wrap_receive_with_body_limit(receive: Receive, *, max_bytes: int) -> Receive:
    total = 0

    async def limited_receive() -> Message:
        nonlocal total
        message = await receive()
        if message["type"] == "http.request":
            total += len(message.get("body", b"") or b"")
            if total > max_bytes:
                raise RequestBodyTooLarge()
        return message

    return limited_receive


def attach_body_byte_limit(request: Request, *, max_bytes: int) -> None:
    """Count streamed body bytes even when Content-Length is omitted."""
    if not should_limit_json_body(request):
        return
    request._receive = wrap_receive_with_body_limit(request.receive, max_bytes=max_bytes)


def json_nesting_too_deep(value: object, *, max_depth: int, _depth: int = 0) -> bool:
    if _depth > max_depth:
        return True
    if isinstance(value, dict):
        return any(
            json_nesting_too_deep(item, max_depth=max_depth, _depth=_depth + 1)
            for item in value.values()
        )
    if isinstance(value, list):
        return any(
            json_nesting_too_deep(item, max_depth=max_depth, _depth=_depth + 1) for item in value
        )
    return False


def json_text_nesting_too_deep(raw: bytes | str, *, max_depth: int) -> bool:
    """Walk JSON text and reject container nesting without calling ``json.loads``.

    CPython's decoder recurses. A few thousand nested objects can raise
    ``RecursionError`` (a 500) long before the parsed tree is inspected.
    """
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return False
    else:
        text = raw

    depth = 0
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char in "{[":
            depth += 1
            if depth > max_depth:
                return True
        elif char in "}]":
            if depth:
                depth -= 1
    return False


def _payload_too_nested_response(request: Request) -> JSONResponse:
    return build_error_response(
        code="PAYLOAD_TOO_NESTED",
        message="Request JSON exceeds the allowed nesting depth.",
        request_id=get_request_id(request),
        status_code=400,
    )


def _is_json_content_type(request: Request) -> bool:
    content_type = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    return content_type == "application/json"


async def reject_deep_json_body(request: Request, *, max_depth: int) -> JSONResponse | None:
    """Reject JSON writes whose object/array nesting exceeds ``max_depth``."""
    if not should_limit_json_body(request) or not _is_json_content_type(request):
        return None
    body = await request.body()
    if not body.strip():
        return None
    if json_text_nesting_too_deep(body, max_depth=max_depth):
        return _payload_too_nested_response(request)
    try:
        parsed = json.loads(body)
    except RecursionError:
        return _payload_too_nested_response(request)
    except json.JSONDecodeError:
        return None
    if not json_nesting_too_deep(parsed, max_depth=max_depth):
        return None
    return _payload_too_nested_response(request)


def payload_too_large_response(request: Request) -> JSONResponse:
    return build_error_response(
        code="PAYLOAD_TOO_LARGE",
        message="Request body exceeds the allowed size.",
        request_id=get_request_id(request),
        status_code=413,
    )


# Keep the type alias used by Starlette receive wrappers visible to tests.
LimitedReceive = Callable[[], Awaitable[Message]]
