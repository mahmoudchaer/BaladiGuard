"""Staff password-reset HTTP and persistence schemas (issue #178)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class StoredStaffPasswordResetChallenge(BaseModel):
    challenge_id: str = Field(alias="challengeId")
    code_hash: str = Field(alias="codeHash")
    staff_id: str = Field(alias="staffId")
    username: str
    created_at: str = Field(alias="createdAt")
    expires_at: str = Field(alias="expiresAt")
    attempt_count: int = Field(default=0, alias="attemptCount")
    consumed_at: str | None = Field(default=None, alias="consumedAt")
    superseded_at: str | None = Field(default=None, alias="supersededAt")
    ttl: int | None = None

    model_config = {"populate_by_name": True}


class StaffPasswordResetRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        trimmed = value.strip().lower()
        if not trimmed:
            raise ValueError("username is required.")
        return trimmed


class StaffPasswordResetRequestResponse(BaseModel):
    """Account-neutral acknowledgement only — never includes challengeId or codes."""

    message: str


class StaffPasswordResetConfirmRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(alias="newPassword", min_length=8, max_length=200)

    model_config = {"populate_by_name": True}

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        trimmed = value.strip().lower()
        if not trimmed:
            raise ValueError("username is required.")
        return trimmed

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed.isdigit() or len(trimmed) != 6:
            raise ValueError("code must be a 6-digit reset code.")
        return trimmed


class StaffPasswordResetConfirmResponse(BaseModel):
    message: str
