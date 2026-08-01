"""Citizen account and profile schemas (issue #169)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

TicketUpdatesPreference = Literal["SMS", "EMAIL", "BOTH", "NONE"]


class NotificationPreferences(BaseModel):
    ticket_updates: TicketUpdatesPreference = Field(default="NONE", alias="ticketUpdates")
    announcements: bool = False

    model_config = {"populate_by_name": True}


class StoredCitizenUser(BaseModel):
    """Persisted citizen identity. Never includes password or OTP/session material."""

    user_id: str = Field(alias="userId")
    phone: str
    phone_verified_at: str = Field(alias="phoneVerifiedAt")
    full_name: str | None = Field(default=None, alias="fullName")
    email: EmailStr | None = None
    notification_preferences: NotificationPreferences = Field(
        default_factory=NotificationPreferences,
        alias="notificationPreferences",
    )
    public_name_visible: bool = Field(default=False, alias="publicNameVisible")
    active: bool = True
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class CitizenProfileResponse(BaseModel):
    """Citizen-safe profile projection returned by GET/PATCH /v1/citizen/me."""

    user_id: str = Field(alias="userId")
    phone: str
    phone_verified_at: str = Field(alias="phoneVerifiedAt")
    full_name: str | None = Field(default=None, alias="fullName")
    email: EmailStr | None = None
    notification_preferences: NotificationPreferences = Field(alias="notificationPreferences")
    public_name_visible: bool = Field(alias="publicNameVisible")
    active: bool
    contribution_ready: bool = Field(alias="contributionReady")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class NotificationPreferencesUpdate(BaseModel):
    ticket_updates: TicketUpdatesPreference | None = Field(default=None, alias="ticketUpdates")
    announcements: bool | None = None

    model_config = {"populate_by_name": True}


class CitizenProfileUpdateRequest(BaseModel):
    """Partial profile update. Phone changes require a verified CHANGE_PHONE OTP."""

    full_name: str | None = Field(default=None, alias="fullName")
    email: EmailStr | None = None
    notification_preferences: NotificationPreferencesUpdate | None = Field(
        default=None,
        alias="notificationPreferences",
    )
    public_name_visible: bool | None = Field(default=None, alias="publicNameVisible")
    phone: str | None = None
    region: str | None = None
    phone_change_challenge_id: str | None = Field(default=None, alias="phoneChangeChallengeId")
    phone_change_code: str | None = Field(default=None, alias="phoneChangeCode")

    model_config = {"populate_by_name": True}

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("fullName must be 1–120 characters after trimming.")
        if len(trimmed) > 120:
            raise ValueError("fullName must be 1–120 characters after trimming.")
        return trimmed

    @model_validator(mode="after")
    def validate_phone_change_fields(self) -> CitizenProfileUpdateRequest:
        phone_present = "phone" in self.model_fields_set and self.phone is not None
        if not phone_present:
            return self
        if not self.phone_change_challenge_id or not self.phone_change_code:
            raise ValueError(
                "phoneChangeChallengeId and phoneChangeCode are required to change phone."
            )
        return self
