from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.errors import build_error_response, get_request_id
from app.schemas.location_validation import ValidateLocationRequest, ValidateLocationResponse
from app.services.location.amazon_location_client import LocationProviderError
from app.services.location.validate_location import validate_location

router = APIRouter(prefix="/v1", tags=["locations"])


@router.post("/locations/validate", response_model=ValidateLocationResponse)
def validate_report_location(
    payload: ValidateLocationRequest,
    request: Request,
) -> ValidateLocationResponse | JSONResponse:
    try:
        result = validate_location(payload)
    except LocationProviderError as exc:
        status_code = 502 if exc.code == "LOCATION_PROVIDER_UNAVAILABLE" else 400
        return build_error_response(
            code=exc.code,
            message=exc.message,
            request_id=get_request_id(request),
            status_code=status_code,
        )

    if not result.success:
        code = "LOCATION_NOT_FOUND"
        message = result.message or "Location validation failed."
        lowered = message.lower()
        if "service area" in lowered:
            code = "LOCATION_OUT_OF_SERVICE_AREA"
        return build_error_response(
            code=code,
            message=message,
            request_id=get_request_id(request),
            status_code=400,
        )

    return result
