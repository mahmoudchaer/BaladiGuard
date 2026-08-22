"""Persisted municipality responsibility profiles (issue #322)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ServiceDomain = Literal[
    "roads",
    "waste",
    "lighting",
    "water",
    "noise",
    "traffic",
    "drainage",
    "facilities",
    "electricity",
]

SERVICE_DOMAINS: frozenset[str] = frozenset(
    {
        "roads",
        "waste",
        "lighting",
        "water",
        "noise",
        "traffic",
        "drainage",
        "facilities",
        "electricity",
    }
)

MunicipalityRoutingStatus = Literal["pending", "assigned", "unassigned"]
MunicipalityRoutingMethod = Literal[
    "deterministic",
    "model",
    "staff_claim",
    "staff_reject",
    "operator_override",
    "deactivation",
    "fallback",
]


class MunicipalityBounds(BaseModel):
    min_latitude: float = Field(ge=-90, le=90, alias="minLatitude")
    max_latitude: float = Field(ge=-90, le=90, alias="maxLatitude")
    min_longitude: float = Field(ge=-180, le=180, alias="minLongitude")
    max_longitude: float = Field(ge=-180, le=180, alias="maxLongitude")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def ordered_box(self) -> MunicipalityBounds:
        if self.min_latitude >= self.max_latitude:
            raise ValueError("minLatitude must be less than maxLatitude.")
        if self.min_longitude >= self.max_longitude:
            raise ValueError("minLongitude must be less than maxLongitude.")
        return self


class GeoPolygon(BaseModel):
    """Closed ring of [longitude, latitude] pairs (GeoJSON order)."""

    coordinates: list[list[float]] = Field(min_length=4, max_length=256)

    model_config = {"extra": "forbid"}

    @field_validator("coordinates")
    @classmethod
    def closed_ring(cls, value: list[list[float]]) -> list[list[float]]:
        for point in value:
            if len(point) != 2:
                raise ValueError("Each polygon vertex must be [longitude, latitude].")
            lon, lat = point
            if not -180 <= lon <= 180 or not -90 <= lat <= 90:
                raise ValueError("Polygon vertices must be valid WGS84 coordinates.")
        if value[0] != value[-1]:
            raise ValueError("Polygon ring must be closed.")
        return value


class MunicipalityContact(BaseModel):
    escalation_email: str | None = Field(default=None, alias="escalationEmail", max_length=254)
    escalation_phone: str | None = Field(default=None, alias="escalationPhone", max_length=32)
    notes: str | None = Field(default=None, max_length=500)

    model_config = {"populate_by_name": True}


class StoredMunicipality(BaseModel):
    municipality_id: str = Field(alias="municipalityId")
    name: str = Field(min_length=1, max_length=160)
    legal_name: str | None = Field(default=None, alias="legalName", max_length=200)
    description: str = Field(min_length=3, max_length=4000)
    city: str | None = Field(default=None, max_length=120)
    governorate: str | None = Field(default=None, max_length=120)
    service_domains: list[ServiceDomain] = Field(alias="serviceDomains")
    bounds: MunicipalityBounds
    polygon: GeoPolygon | None = None
    category_ids: list[str] = Field(default_factory=list, alias="categoryIds")
    contact: MunicipalityContact | None = None
    active: bool = True
    profile_version: int = Field(default=1, alias="profileVersion", ge=1)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}

    @field_validator("name", "description")
    @classmethod
    def strip_required(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("must not be blank.")
        return trimmed

    @field_validator("service_domains")
    @classmethod
    def unique_domains(cls, value: list[ServiceDomain]) -> list[ServiceDomain]:
        if not value:
            raise ValueError("serviceDomains must not be empty.")
        seen: set[str] = set()
        ordered: list[ServiceDomain] = []
        for domain in value:
            if domain in seen:
                continue
            seen.add(domain)
            ordered.append(domain)
        return ordered


class MunicipalityRoutingDecision(BaseModel):
    status: MunicipalityRoutingStatus
    municipality_id: str | None = Field(default=None, alias="municipalityId")
    suggested_municipality_id: str | None = Field(default=None, alias="suggestedMunicipalityId")
    confidence: float | None = Field(default=None, ge=0, le=1)
    method: MunicipalityRoutingMethod
    reason_code: str = Field(alias="reasonCode")
    reason: str
    profile_version: int | None = Field(default=None, alias="profileVersion")
    eligible_municipality_ids: list[str] = Field(
        default_factory=list, alias="eligibleMunicipalityIds"
    )
    model_id: str | None = Field(default=None, alias="modelId")

    model_config = {"populate_by_name": True}


class MunicipalityRoutingProvenance(MunicipalityRoutingDecision):
    actor_id: str | None = Field(default=None, alias="actorId")
    actor_role: str | None = Field(default=None, alias="actorRole")
    note: str | None = None
    recorded_at: str = Field(alias="recordedAt")

    model_config = {"populate_by_name": True}
