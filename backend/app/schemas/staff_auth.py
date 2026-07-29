"""Staff authentication request/response schemas (issue #72)."""

from pydantic import BaseModel, Field


class StaffLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=200)

    model_config = {"populate_by_name": True}


class StaffLoginResponse(BaseModel):
    access_token: str = Field(alias="accessToken")
    token_type: str = Field(default="Bearer", alias="tokenType")
    username: str
    expires_in: int = Field(alias="expiresIn")

    model_config = {"populate_by_name": True}
