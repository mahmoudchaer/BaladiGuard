"""Persisted staff account schemas (issue #175)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

StaffRole = Literal["municipal_staff", "administrator"]


class StoredStaffUser(BaseModel):
    """Staff identity + credential metadata. Password hashes never leave the store layer."""

    staff_id: str = Field(alias="staffId")
    username: str
    name: str
    email: EmailStr
    password_hash: str = Field(alias="passwordHash")
    role: StaffRole
    municipality_id: str | None = Field(default=None, alias="municipalityId")
    department_ids: list[str] | None = Field(default=None, alias="departmentIds")
    active: bool = True
    session_epoch: int = Field(default=0, alias="sessionEpoch", ge=0)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        trimmed = value.strip().lower()
        if not trimmed or len(trimmed) > 120:
            raise ValueError("username must be 1–120 characters.")
        return trimmed

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed or len(trimmed) > 120:
            raise ValueError("name must be 1–120 characters.")
        return trimmed

    @model_validator(mode="after")
    def validate_role_scope(self) -> StoredStaffUser:
        if self.role == "administrator":
            if self.municipality_id is not None or self.department_ids is not None:
                raise ValueError(
                    "administrator accounts must use municipalityId=null and departmentIds=null."
                )
            return self
        if not self.municipality_id:
            raise ValueError("municipal_staff accounts require municipalityId.")
        if self.department_ids is None or len(self.department_ids) == 0:
            raise ValueError("municipal_staff accounts require a non-empty departmentIds list.")
        return self


def staff_username_claim_key(username: str) -> str:
    return f"USERNAME#{username.strip().lower()}"
