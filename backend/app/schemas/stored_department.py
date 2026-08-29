"""Persisted municipality department mappings (issue #322)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.stored_municipality import ServiceDomain


class StoredDepartment(BaseModel):
    department_id: str = Field(alias="departmentId")
    municipality_id: str = Field(alias="municipalityId")
    name: str
    description: str
    service_domain: ServiceDomain = Field(alias="serviceDomain")

    model_config = {"populate_by_name": True}
