"""Create one department per service domain when a municipality is provisioned."""

from __future__ import annotations

from uuid import uuid4

from app.database.store_factory import get_department_store
from app.schemas.municipality import MunicipalityResponse
from app.schemas.stored_department import StoredDepartment
from app.schemas.stored_municipality import StoredMunicipality

DOMAIN_DEPARTMENT_NAMES: dict[str, str] = {
    "roads": "Road Maintenance",
    "waste": "Waste Management",
    "lighting": "Street Lighting",
    "water": "Water Distribution",
    "noise": "Noise Control",
    "traffic": "Traffic Management",
    "drainage": "Drainage",
    "facilities": "Public Facilities",
    "electricity": "Power Distribution",
}


def departments_for_municipality(municipality_id: str) -> list[StoredDepartment]:
    return get_department_store().list_by_municipality(municipality_id)


def ensure_departments_for_profile(profile: StoredMunicipality) -> list[StoredDepartment]:
    """Idempotently create a department for each service domain on the profile."""
    store = get_department_store()
    existing = store.list_by_municipality(profile.municipality_id)
    by_domain = {item.service_domain: item for item in existing}
    for domain in profile.service_domains:
        if domain in by_domain:
            continue
        name = DOMAIN_DEPARTMENT_NAMES.get(domain, domain.replace("_", " ").title())
        stored = store.put(
            StoredDepartment(
                departmentId=str(uuid4()),
                municipalityId=profile.municipality_id,
                name=name,
                description=f"Handles {domain} reports for {profile.name}.",
                serviceDomain=domain,
            )
        )
        existing.append(stored)
    existing.sort(key=lambda item: item.name.lower())
    return existing


def municipality_response(profile: StoredMunicipality) -> MunicipalityResponse:
    return MunicipalityResponse.from_stored(
        profile,
        departments=departments_for_municipality(profile.municipality_id),
    )
