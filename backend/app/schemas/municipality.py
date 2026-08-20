"""HTTP models for developer municipality management and ticket routing (#322)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.stored_municipality import (
    MunicipalityBounds,
    MunicipalityContact,
    MunicipalityRoutingDecision,
    MunicipalityRoutingProvenance,
    ServiceDomain,
    StoredMunicipality,
)

MunicipalityRejectReason = Literal[
    "OUT_OF_GEOGRAPHY",
    "OUT_OF_SERVICE",
    "WRONG_AUTHORITY",
    "INACTIVE_PROFILE",
    "OTHER",
]
MunicipalityClaimReason = Literal[
    "CONFIRMED_GEOGRAPHY",
    "CONFIRMED_SERVICE",
    "STAFF_KNOWLEDGE",
]
MunicipalityOverrideReason = Literal[
    "PROFILE_CORRECTION",
    "ROUTING_ERROR",
    "DEVELOPER_REASSIGN",
    "DEACTIVATION_TRANSFER",
]


class MunicipalityResponse(BaseModel):
    municipality_id: str = Field(alias="municipalityId")
    name: str
    legal_name: str | None = Field(default=None, alias="legalName")
    description: str
    city: str | None = None
    governorate: str | None = None
    service_domains: list[ServiceDomain] = Field(alias="serviceDomains")
    bounds: MunicipalityBounds
    polygon: dict | None = None
    category_ids: list[str] = Field(default_factory=list, alias="categoryIds")
    contact: MunicipalityContact | None = None
    active: bool
    profile_version: int = Field(alias="profileVersion")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_stored(cls, item: StoredMunicipality) -> MunicipalityResponse:
        polygon = None
        if item.polygon is not None:
            polygon = {"coordinates": item.polygon.coordinates}
        return cls.model_validate(
            {
                **item.model_dump(by_alias=True),
                "polygon": polygon,
            }
        )


class MunicipalityListResponse(BaseModel):
    items: list[MunicipalityResponse]


class UpsertMunicipalityRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    legal_name: str | None = Field(default=None, alias="legalName", max_length=200)
    description: str = Field(min_length=3, max_length=4000)
    city: str | None = Field(default=None, max_length=120)
    governorate: str | None = Field(default=None, max_length=120)
    service_domains: list[ServiceDomain] = Field(alias="serviceDomains")
    bounds: MunicipalityBounds
    polygon: dict | None = None
    category_ids: list[str] = Field(default_factory=list, alias="categoryIds")
    contact: MunicipalityContact | None = None
    active: bool = True

    model_config = {"populate_by_name": True}

    @field_validator("name", "description")
    @classmethod
    def strip_required(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("must not be blank.")
        return trimmed


class ProvisionMunicipalityAdminRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class ProvisionMunicipalityAdminResponse(BaseModel):
    staff_id: str = Field(alias="staffId")
    username: str
    municipality_id: str = Field(alias="municipalityId")
    role: Literal["administrator"] = "administrator"

    model_config = {"populate_by_name": True}


class RoutingPreviewRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    category: str | None = None
    description: str | None = Field(default=None, max_length=4000)
    use_model: bool = Field(default=False, alias="useModel")

    model_config = {"populate_by_name": True}


class RoutingPreviewResponse(BaseModel):
    decision: MunicipalityRoutingDecision
    eligible: list[MunicipalityResponse] = Field(default_factory=list)


class MunicipalityRoutingActionRequest(BaseModel):
    expected_updated_at: str | None = Field(default=None, alias="expectedUpdatedAt")
    note: str | None = Field(default=None, max_length=500)

    model_config = {"populate_by_name": True}

    @field_validator("note")
    @classmethod
    def bound_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class MunicipalityRejectRequest(MunicipalityRoutingActionRequest):
    reason_code: MunicipalityRejectReason = Field(alias="reasonCode")

    model_config = {"populate_by_name": True}


class MunicipalityClaimRequest(MunicipalityRoutingActionRequest):
    reason_code: MunicipalityClaimReason = Field(alias="reasonCode")

    model_config = {"populate_by_name": True}


class MunicipalityOverrideRequest(MunicipalityRoutingActionRequest):
    municipality_id: str | None = Field(default=None, alias="municipalityId")
    reason_code: MunicipalityOverrideReason = Field(alias="reasonCode")

    model_config = {"populate_by_name": True}


class TicketMunicipalityRouting(BaseModel):
    status: str | None = None
    decision: MunicipalityRoutingDecision | None = None
    history: list[MunicipalityRoutingProvenance] = Field(default_factory=list)
    can_claim: bool = Field(alias="canClaim")
    can_reject: bool = Field(alias="canReject")
    can_override: bool = Field(alias="canOverride")

    model_config = {"populate_by_name": True}
