"""Safe administrator HTTP models for staff-account management (issue #236)."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.staff_user import MunicipalityAssignableRole, StaffRole, StoredStaffUser


class StaffAccountResponse(BaseModel):
    staff_id: str = Field(alias="staffId")
    username: str
    name: str
    email: EmailStr
    role: StaffRole
    municipality_id: str | None = Field(alias="municipalityId")
    department_ids: list[str] | None = Field(alias="departmentIds")
    active: bool
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_user(cls, user: StoredStaffUser) -> StaffAccountResponse:
        return cls(
            staffId=user.staff_id,
            username=user.username,
            name=user.name,
            email=user.email,
            role=user.role,
            municipalityId=user.municipality_id,
            departmentIds=user.department_ids,
            active=user.active,
            createdAt=user.created_at,
            updatedAt=user.updated_at,
        )


class CreateStaffAccountRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    role: MunicipalityAssignableRole
    municipality_id: str | None = Field(default=None, alias="municipalityId")
    department_ids: list[str] | None = Field(default=None, alias="departmentIds")

    model_config = {"populate_by_name": True}

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class UpdateStaffAccountRequest(BaseModel):
    role: MunicipalityAssignableRole | None = None
    municipality_id: str | None = Field(default=None, alias="municipalityId")
    department_ids: list[str] | None = Field(default=None, alias="departmentIds")

    model_config = {"populate_by_name": True}

    @field_validator("role")
    @classmethod
    def role_cannot_be_null(
        cls, value: MunicipalityAssignableRole | None
    ) -> MunicipalityAssignableRole | None:
        if value is None:
            raise ValueError("role cannot be null when supplied.")
        return value
