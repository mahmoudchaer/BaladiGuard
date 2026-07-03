import re
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

LocationSource = Literal["GPS", "MANUAL", "PLACEHOLDER"]
PreferredChannel = Literal["SMS", "EMAIL"]
TicketStatus = Literal["SUBMITTED"]

PHONE_PATTERN = re.compile(r"^\+?[0-9\s()-]{7,20}$")


class ClientMetadata(BaseModel):
    platform: str = Field(min_length=1, max_length=40)
    app_version: str = Field(alias="appVersion", min_length=1, max_length=40)

    model_config = {"populate_by_name": True}


class ReportContact(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    preferred_channel: PreferredChannel | None = Field(default=None, alias="preferredChannel")

    model_config = {"populate_by_name": True}

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        trimmed = value.strip()
        if not trimmed:
            return None
        if not PHONE_PATTERN.match(trimmed):
            raise ValueError("Enter a valid phone number.")
        return trimmed

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        trimmed = value.strip()
        return trimmed or None

    @model_validator(mode="after")
    def require_phone_or_email(self) -> "ReportContact":
        if not self.phone and not self.email:
            raise ValueError("Provide a phone number or email so we can reach you.")
        return self


class ReportLocation(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address_text: str = Field(alias="addressText", min_length=3, max_length=500)
    source: LocationSource

    model_config = {"populate_by_name": True}

    @field_validator("address_text")
    @classmethod
    def normalize_address(cls, value: str) -> str:
        return value.strip()


class SubmitTicketRequest(BaseModel):
    description: str = Field(min_length=10, max_length=2000)
    language_hint: str = Field(default="auto", alias="languageHint", min_length=1, max_length=40)
    contact: ReportContact
    location: ReportLocation
    image_object_key: str = Field(alias="imageObjectKey", min_length=1, max_length=500)
    client_metadata: ClientMetadata = Field(alias="clientMetadata")

    model_config = {"populate_by_name": True}

    @field_validator("description", "image_object_key")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("This field is required.")
        return trimmed


class SubmitTicketResponse(BaseModel):
    ticket_id: str = Field(alias="ticketId")
    ticket_number: str = Field(alias="ticketNumber")
    tracking_code: str = Field(alias="trackingCode")
    status: TicketStatus
    message: str
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}
