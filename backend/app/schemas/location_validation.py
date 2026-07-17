from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.ticket import LocationSource, ReportLocation

LocationValidationMode = Literal["address", "coordinates"]


class ValidateLocationRequest(BaseModel):
    address_text: str | None = Field(default=None, alias="addressText", max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    model_config = {"populate_by_name": True}

    @field_validator("address_text", mode="before")
    @classmethod
    def normalize_address(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def validate_finite_coordinate(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, bool):
            raise ValueError("Coordinate must be a finite number.")
        if isinstance(value, (int, float)) and not math.isfinite(value):
            raise ValueError("Coordinate must be a finite number.")
        return value

    @model_validator(mode="after")
    def require_address_or_coordinates(self) -> ValidateLocationRequest:
        has_address = bool(self.address_text)
        has_latitude = self.latitude is not None
        has_longitude = self.longitude is not None

        if has_latitude != has_longitude:
            raise ValueError("Provide both latitude and longitude together.")

        if not has_address and not (has_latitude and has_longitude):
            raise ValueError("Provide an addressText or a latitude/longitude pair.")

        if has_address and len(self.address_text or "") < 3:
            raise ValueError("addressText must be at least 3 characters.")

        return self

    @property
    def mode(self) -> LocationValidationMode:
        if self.latitude is not None and self.longitude is not None:
            return "coordinates"
        return "address"


class ValidatedLocation(BaseModel):
    latitude: float
    longitude: float
    address_text: str = Field(alias="addressText")
    source: LocationSource

    model_config = {"populate_by_name": True}


class ValidateLocationResponse(BaseModel):
    success: bool
    location: ValidatedLocation | None = None
    message: str | None = None

    model_config = {"populate_by_name": True}


def to_report_location(location: ValidatedLocation) -> ReportLocation:
    return ReportLocation(
        latitude=location.latitude,
        longitude=location.longitude,
        addressText=location.address_text,
        source=location.source,
    )
