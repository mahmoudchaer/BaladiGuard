"""Pre-body abuse controls for public photo upload (issue #186).

FastAPI resolves ``UploadFile = File(...)`` before the route body runs, which
spools multipart payloads. These checks must run in HTTP middleware *before*
``call_next`` so oversized or rate-limited uploads never reach multipart parsing.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.errors import build_error_response, get_request_id
from app.core.rate_limit import enforce_rate_limit
from app.services.uploads.photo_upload_service import MAX_IMAGE_SIZE_BYTES

REPORT_PHOTO_UPLOAD_PATH = "/v1/uploads/report-photo"
# Multipart framing adds boundaries/headers beyond the raw file bytes.
MAX_UPLOAD_REQUEST_BYTES = MAX_IMAGE_SIZE_BYTES + (256 * 1024)


def is_report_photo_upload(request: Request) -> bool:
    path = request.url.path.rstrip("/") or "/"
    return request.method == "POST" and path == REPORT_PHOTO_UPLOAD_PATH


def reject_upload_abuse_early(request: Request) -> JSONResponse | None:
    """Reject oversized or over-quota upload requests before the body is parsed."""
    if not is_report_photo_upload(request):
        return None

    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.strip():
        try:
            size = int(content_length.strip())
        except ValueError:
            return build_error_response(
                code="VALIDATION_ERROR",
                message="Content-Length must be a valid integer.",
                request_id=get_request_id(request),
                status_code=400,
            )
        if size < 0:
            return build_error_response(
                code="VALIDATION_ERROR",
                message="Content-Length must be a non-negative integer.",
                request_id=get_request_id(request),
                status_code=400,
            )
        if size > MAX_UPLOAD_REQUEST_BYTES:
            return build_error_response(
                code="FILE_TOO_LARGE",
                message="Image file must be 5MB or smaller.",
                request_id=get_request_id(request),
                status_code=400,
            )

    return enforce_rate_limit(
        request,
        "public-upload-report-photo",
        message="Too many upload requests. Please wait before trying again.",
    )
