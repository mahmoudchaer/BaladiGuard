"""Standalone location validation service for issue #24."""

from __future__ import annotations

from app.schemas.location_validation import (
    ValidatedLocation,
    ValidateLocationRequest,
    ValidateLocationResponse,
)
from app.services.location.amazon_location_client import (
    LocationProvider,
    LocationProviderError,
    location_provider,
)


def validate_location(
    payload: ValidateLocationRequest,
    *,
    provider: LocationProvider | None = None,
) -> ValidateLocationResponse:
    """Validate address or coordinate input and return a normalized location."""
    active_provider = provider or location_provider

    try:
        if payload.mode == "coordinates":
            assert payload.latitude is not None and payload.longitude is not None
            result = active_provider.reverse_geocode(payload.latitude, payload.longitude)
            source = "GPS"
        else:
            assert payload.address_text is not None
            result = active_provider.geocode_address(payload.address_text)
            source = "MANUAL"
    except LocationProviderError as exc:
        return ValidateLocationResponse(success=False, message=exc.message)

    location = ValidatedLocation(
        latitude=float(result["latitude"]),
        longitude=float(result["longitude"]),
        addressText=str(result["addressText"]).strip(),
        source=source,
    )
    return ValidateLocationResponse(
        success=True,
        location=location,
        message="Location validated successfully.",
    )
