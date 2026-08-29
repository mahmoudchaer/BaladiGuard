"""Citizen account and profile schemas (issue #169)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.schemas.rewards import CitizenRewardsExport
from app.schemas.ticket_status import TicketStatus

TicketUpdatesPreference = Literal["SMS", "EMAIL", "BOTH", "NONE"]
LegalAcceptanceSource = Literal["otp_verify", "profile", "reacceptance"]


class CitizenPushDevice(BaseModel):
    device_id: str = Field(alias="deviceId", min_length=8, max_length=128)
    token: str = Field(min_length=16, max_length=512)
    platform: Literal["ios", "android"]
    app_environment: Literal["development", "staging", "production"] = Field(alias="appEnvironment")
    last_seen_at: str = Field(alias="lastSeenAt")
    active: bool = True

    model_config = {"populate_by_name": True}


class CitizenPushDeviceRequest(BaseModel):
    device_id: str = Field(alias="deviceId", min_length=8, max_length=128)
    token: str = Field(min_length=16, max_length=512)
    platform: Literal["ios", "android"]
    app_environment: Literal["development", "staging", "production"] = Field(alias="appEnvironment")

    model_config = {"populate_by_name": True}


class NotificationPreferences(BaseModel):
    """Ordinary ticket-update preferences. Security/OTP delivery is intentionally separate."""

    ticket_updates: TicketUpdatesPreference = Field(default="NONE", alias="ticketUpdates")
    preference_version: int = Field(default=1, alias="preferenceVersion", ge=1)
    push_enabled: bool = Field(default=False, alias="pushEnabled")
    email_enabled: bool = Field(default=False, alias="emailEnabled")
    whatsapp_enabled: bool = Field(default=False, alias="whatsAppEnabled")
    report_created: bool = Field(default=True, alias="reportCreated")
    status_changes: bool = Field(default=True, alias="statusChanges")
    work_updates: bool = Field(default=True, alias="workUpdates")
    resolution_updates: bool = Field(default=True, alias="resolutionUpdates")
    action_requests: bool = Field(default=True, alias="actionRequests")
    announcements: bool = False

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_ticket_updates(cls, value):
        if not isinstance(value, dict):
            return value
        if any(
            key in value
            for key in (
                "pushEnabled",
                "push_enabled",
                "emailEnabled",
                "email_enabled",
                "whatsAppEnabled",
                "whatsapp_enabled",
            )
        ):
            return value
        legacy = value.get("ticketUpdates", value.get("ticket_updates", "NONE"))
        migrated = dict(value)
        migrated["emailEnabled"] = legacy in {"EMAIL", "BOTH"}
        migrated["whatsAppEnabled"] = legacy in {"SMS", "BOTH"}
        migrated["pushEnabled"] = False
        return migrated

    model_config = {"populate_by_name": True}


class LegalAcceptance(BaseModel):
    """Recorded acceptance of the current legal package (issue #321)."""

    terms_version: str = Field(alias="termsVersion")
    privacy_version: str = Field(alias="privacyVersion")
    acceptable_use_version: str = Field(alias="acceptableUseVersion")
    accepted_at: str = Field(alias="acceptedAt")
    locale: str | None = None
    source: LegalAcceptanceSource = "otp_verify"

    model_config = {"populate_by_name": True}


class LegalAcceptanceRequest(BaseModel):
    """Body for POST /v1/citizen/me/legal-acceptance."""

    accept_legal: bool = Field(alias="acceptLegal")
    locale: str | None = None

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
    leaderboard_opt_in: bool = Field(default=False, alias="leaderboardOptIn")
    legal_acceptance: LegalAcceptance | None = Field(default=None, alias="legalAcceptance")
    push_devices: list[CitizenPushDevice] = Field(default_factory=list, alias="pushDevices")
    active: bool = True
    # Bumped on account-wide session revocation (phone change, deactivation, etc.).
    # Not returned from profile endpoints.
    session_epoch: int = Field(default=0, alias="sessionEpoch", ge=0)
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
    push_available: bool = Field(default=False, alias="pushAvailable")
    public_name_visible: bool = Field(alias="publicNameVisible")
    leaderboard_opt_in: bool = Field(alias="leaderboardOptIn")
    active: bool
    contribution_ready: bool = Field(alias="contributionReady")
    legal_acceptance: LegalAcceptance | None = Field(default=None, alias="legalAcceptance")
    legal_acceptance_required: bool = Field(alias="legalAcceptanceRequired")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class NotificationPreferencesUpdate(BaseModel):
    ticket_updates: TicketUpdatesPreference | None = Field(default=None, alias="ticketUpdates")
    push_enabled: bool | None = Field(default=None, alias="pushEnabled")
    email_enabled: bool | None = Field(default=None, alias="emailEnabled")
    whatsapp_enabled: bool | None = Field(default=None, alias="whatsAppEnabled")
    report_created: bool | None = Field(default=None, alias="reportCreated")
    status_changes: bool | None = Field(default=None, alias="statusChanges")
    work_updates: bool | None = Field(default=None, alias="workUpdates")
    resolution_updates: bool | None = Field(default=None, alias="resolutionUpdates")
    action_requests: bool | None = Field(default=None, alias="actionRequests")
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
    leaderboard_opt_in: bool | None = Field(default=None, alias="leaderboardOptIn")
    phone: str | None = None
    region: str | None = None
    phone_change_challenge_id: str | None = Field(default=None, alias="phoneChangeChallengeId")
    phone_change_code: str | None = Field(default=None, alias="phoneChangeCode")

    model_config = {"populate_by_name": True}

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str | None) -> str | None:
        """Optional profile field (#270). Blank clears to null; non-empty must be 1–120."""
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
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


class CitizenExportTicketSummary(BaseModel):
    """Owned-ticket projection included in a citizen privacy export (issue #190)."""

    ticket_id: str = Field(alias="ticketId")
    ticket_number: str = Field(alias="ticketNumber")
    tracking_code: str = Field(alias="trackingCode")
    status: str
    category: str
    description: str
    location_address: str = Field(alias="locationAddress")
    created_at: str = Field(alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class CitizenTicketHistoryItem(BaseModel):
    """Citizen-owned ticket history projection for the mobile account screen."""

    tracking_code: str = Field(alias="trackingCode")
    status: TicketStatus
    category: str | None = None
    location_address: str = Field(alias="locationAddress")
    submitted_at: str = Field(alias="submittedAt")
    can_submit_resolution_feedback: bool = Field(default=False, alias="canSubmitResolutionFeedback")
    resolution_feedback_status: str | None = Field(default=None, alias="resolutionFeedbackStatus")

    model_config = {"populate_by_name": True}


class CitizenTicketHistoryResponse(BaseModel):
    """Bounded page of authenticated citizen-owned ticket history."""

    items: list[CitizenTicketHistoryItem]
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    limit: int = Field(ge=1, le=50)

    model_config = {"populate_by_name": True}


class CitizenDataExportResponse(BaseModel):
    """Authenticated citizen self-service data export (issue #190)."""

    exported_at: str = Field(alias="exportedAt")
    profile: CitizenProfileResponse
    tickets: list[CitizenExportTicketSummary]
    rewards: CitizenRewardsExport | None = None

    model_config = {"populate_by_name": True}


class CitizenDeleteResponse(BaseModel):
    """Acknowledgement body for account anonymization (issue #190)."""

    status: Literal["deleted"] = "deleted"
    user_id: str = Field(alias="userId")
    deleted_at: str = Field(alias="deletedAt")

    model_config = {"populate_by_name": True}
