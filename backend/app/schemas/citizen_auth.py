"""Citizen OTP authentication HTTP schemas (issue #170)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.citizen import CitizenProfileResponse, LegalAcceptance, NotificationPreferences

OtpPurpose = Literal["LOGIN_OR_SIGNUP", "CHANGE_PHONE"]


class CitizenOtpRequest(BaseModel):
    phone: str = Field(min_length=1, max_length=32)
    region: str | None = Field(default=None, min_length=2, max_length=2)
    purpose: OtpPurpose = "LOGIN_OR_SIGNUP"

    model_config = {"populate_by_name": True}

    @field_validator("phone")
    @classmethod
    def strip_phone(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("phone is required.")
        return trimmed

    @field_validator("region")
    @classmethod
    def normalize_region(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip().upper()
        if len(trimmed) != 2 or not trimmed.isalpha():
            raise ValueError("region must be an ISO 3166-1 alpha-2 code.")
        return trimmed


class CitizenOtpRequestResponse(BaseModel):
    challenge_id: str = Field(alias="challengeId")
    expires_in: int = Field(alias="expiresIn")
    message: str
    # Adaptable UI hint only — never proves delivery success or account existence (#297).
    delivery_channel: Literal["sms", "whatsapp", "dev"] = Field(
        default="sms",
        alias="deliveryChannel",
    )

    model_config = {"populate_by_name": True}


class CitizenOtpVerifyRequest(BaseModel):
    challenge_id: str = Field(alias="challengeId", min_length=1, max_length=80)
    code: str = Field(min_length=4, max_length=12)
    full_name: str | None = Field(default=None, alias="fullName")
    accept_legal: bool | None = Field(default=None, alias="acceptLegal")
    legal_locale: str | None = Field(default=None, alias="legalLocale", max_length=16)

    model_config = {"populate_by_name": True}

    @field_validator("challenge_id")
    @classmethod
    def strip_challenge_id(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("challengeId is required.")
        return trimmed

    @field_validator("code")
    @classmethod
    def strip_code(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("code is required.")
        return trimmed

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
    def code_is_digits(self) -> CitizenOtpVerifyRequest:
        if not self.code.isdigit() or len(self.code) != 6:
            raise ValueError("code must be a 6-digit verification code.")
        return self


class CitizenOtpVerifyResponse(BaseModel):
    # Browser cookie sessions intentionally omit the raw opaque token. Mobile
    # keeps receiving it for platform-secure storage.
    access_token: str | None = Field(default=None, alias="accessToken")
    token_type: str = Field(default="Bearer", alias="tokenType")
    expires_in: int = Field(alias="expiresIn")
    user_id: str = Field(alias="userId")
    phone: str
    phone_verified_at: str = Field(alias="phoneVerifiedAt")
    full_name: str | None = Field(default=None, alias="fullName")
    email: str | None = None
    notification_preferences: NotificationPreferences = Field(alias="notificationPreferences")
    public_name_visible: bool = Field(alias="publicNameVisible")
    leaderboard_opt_in: bool = Field(alias="leaderboardOptIn")
    active: bool
    contribution_ready: bool = Field(alias="contributionReady")
    legal_acceptance: LegalAcceptance | None = Field(default=None, alias="legalAcceptance")
    legal_acceptance_required: bool = Field(default=True, alias="legalAcceptanceRequired")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_session(
        cls,
        *,
        access_token: str,
        expires_in: int,
        profile: CitizenProfileResponse,
    ) -> CitizenOtpVerifyResponse:
        return cls(
            accessToken=access_token,
            tokenType="Bearer",
            expiresIn=expires_in,
            userId=profile.user_id,
            phone=profile.phone,
            phoneVerifiedAt=profile.phone_verified_at,
            fullName=profile.full_name,
            email=profile.email,
            notificationPreferences=profile.notification_preferences,
            publicNameVisible=profile.public_name_visible,
            leaderboardOptIn=profile.leaderboard_opt_in,
            active=profile.active,
            contributionReady=profile.contribution_ready,
            legalAcceptance=profile.legal_acceptance,
            legalAcceptanceRequired=profile.legal_acceptance_required,
            createdAt=profile.created_at,
            updatedAt=profile.updated_at,
        )
