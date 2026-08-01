from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.errors import build_error_response, get_request_id
from app.core.rate_limit import enforce_rate_limit
from app.services.uploads.photo_upload_service import (
    InvalidUploadError,
    S3UploadError,
    photo_upload_service,
)

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])
REPORT_PHOTO_FILE = File(default=None)


class ReportPhotoUploadResponse(BaseModel):
    image_object_key: str = Field(serialization_alias="imageObjectKey")


@router.post("/report-photo", response_model=ReportPhotoUploadResponse)
async def upload_report_photo(
    request: Request,
    file: UploadFile | None = REPORT_PHOTO_FILE,
) -> ReportPhotoUploadResponse | JSONResponse:
    limited = enforce_rate_limit(
        request,
        "public-upload-report-photo",
        message="Too many upload requests. Please wait before trying again.",
    )
    if limited is not None:
        return limited

    if file is None:
        return build_error_response(
            code="MISSING_FILE",
            message="An image file is required.",
            request_id=get_request_id(request),
            status_code=400,
        )

    try:
        image_object_key = await photo_upload_service.upload_report_photo(file)
    except InvalidUploadError as exc:
        return build_error_response(
            code=exc.code,
            message=exc.message,
            request_id=get_request_id(request),
            status_code=400,
        )
    except S3UploadError:
        return build_error_response(
            code="S3_UPLOAD_FAILED",
            message="Failed to upload image to storage.",
            request_id=get_request_id(request),
            status_code=502,
        )

    return ReportPhotoUploadResponse(image_object_key=image_object_key)
