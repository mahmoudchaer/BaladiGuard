"""Staff authentication request/response schemas (issue #175)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

StaffRole = Literal["municipal_staff", "administrator", "developer_operator"]


class StaffLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=200)

    model_config = {"populate_by_name": True}


class StaffLoginResponse(BaseModel):
    access_token: str = Field(alias="accessToken")
    token_type: str = Field(default="Bearer", alias="tokenType")
    staff_id: str = Field(alias="staffId")
    username: str
    name: str
    role: StaffRole
    municipality_id: str | None = Field(alias="municipalityId")
    department_ids: list[str] | None = Field(alias="departmentIds")
    expires_in: int = Field(alias="expiresIn")

    model_config = {"populate_by_name": True}
