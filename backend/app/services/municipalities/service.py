"""Developer municipality control plane (issue #322)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

from app.core.password_hashing import hash_password
from app.core.staff_auth import StaffPrincipal
from app.database.staff_store import StaffUsernameConflictError
from app.schemas.municipality import (
    ProvisionMunicipalityAdminRequest,
    ProvisionMunicipalityAdminResponse,
    RoutingPreviewRequest,
    RoutingPreviewResponse,
    UpsertMunicipalityRequest,
)
from app.schemas.staff_user import StoredStaffUser
from app.schemas.stored_municipality import (
    GeoPolygon,
    StoredMunicipality,
)
from app.services.municipalities.departments import ensure_departments_for_profile
from app.services.routing.municipality_router import route_ticket_to_municipality
from app.services.staff.account_audit import account_audit_service


class MunicipalityControlError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _polygon_from_payload(raw: dict | None) -> GeoPolygon | None:
    if raw is None:
        return None
    return GeoPolygon.model_validate(raw)


class MunicipalityControlService:
    def __init__(self, store=None, staff_store=None, ticket_store=None, audit=None) -> None:
        self._store = store
        self._staff_store = staff_store
        self._ticket_store = ticket_store
        self._audit = audit or account_audit_service

    def store(self):
        if self._store is not None:
            return self._store
        from app.database.store_factory import get_municipality_store

        return get_municipality_store()

    def staff_store(self):
        if self._staff_store is not None:
            return self._staff_store
        from app.database.store_factory import get_staff_store

        return get_staff_store()

    def ticket_store(self):
        if self._ticket_store is not None:
            return self._ticket_store
        from app.database.store_factory import get_ticket_store

        return get_ticket_store()

    def list_profiles(self) -> list[StoredMunicipality]:
        return self.store().list_all()

    def get_profile(self, municipality_id: str) -> StoredMunicipality:
        profile = self.store().get(municipality_id)
        if profile is None:
            raise MunicipalityControlError("Municipality was not found.", status_code=404)
        return profile

    def create_profile(
        self, actor: StaffPrincipal, payload: UpsertMunicipalityRequest
    ) -> StoredMunicipality:
        stamped = _iso_now()
        try:
            profile = StoredMunicipality(
                municipalityId=str(uuid4()),
                name=payload.name,
                legalName=payload.legal_name,
                description=payload.description,
                city=payload.city,
                governorate=payload.governorate,
                serviceDomains=payload.service_domains,
                bounds=payload.bounds,
                polygon=_polygon_from_payload(payload.polygon),
                categoryIds=list(payload.category_ids),
                contact=payload.contact,
                active=payload.active,
                profileVersion=1,
                createdAt=stamped,
                updatedAt=stamped,
            )
        except ValidationError as exc:
            raise MunicipalityControlError("Municipality profile is invalid.") from exc
        stored = self.store().put(profile)
        ensure_departments_for_profile(stored)
        self._audit.record_safe(
            action_type="STAFF_CREATED",
            actor=actor,
            target_staff_id=actor.staff_id,
            summary=f"Municipality created: {stored.name}.",
            previous_value=None,
            new_value={"municipalityId": stored.municipality_id, "name": stored.name},
            created_at=stamped,
        )
        return stored

    def update_profile(
        self,
        actor: StaffPrincipal,
        municipality_id: str,
        payload: UpsertMunicipalityRequest,
    ) -> StoredMunicipality:
        current = self.get_profile(municipality_id)
        stamped = _iso_now()
        try:
            updated = current.model_copy(
                update={
                    "name": payload.name,
                    "legal_name": payload.legal_name,
                    "description": payload.description,
                    "city": payload.city,
                    "governorate": payload.governorate,
                    "service_domains": payload.service_domains,
                    "bounds": payload.bounds,
                    "polygon": _polygon_from_payload(payload.polygon),
                    "category_ids": list(payload.category_ids),
                    "contact": payload.contact,
                    "active": payload.active,
                    "profile_version": current.profile_version + 1,
                    "updated_at": stamped,
                }
            )
        except ValidationError as exc:
            raise MunicipalityControlError("Municipality profile is invalid.") from exc
        stored = self.store().put(updated)
        ensure_departments_for_profile(stored)
        if current.active and not stored.active:
            self._park_active_tickets(actor, stored, stamped)
        return stored

    def set_active(
        self, actor: StaffPrincipal, municipality_id: str, *, active: bool
    ) -> StoredMunicipality:
        current = self.get_profile(municipality_id)
        stamped = _iso_now()
        stored = self.store().put(
            current.model_copy(
                update={
                    "active": active,
                    "profile_version": current.profile_version + 1,
                    "updated_at": stamped,
                }
            )
        )
        if current.active and not active:
            self._park_active_tickets(actor, stored, stamped)
        return stored

    def provision_admin(
        self,
        actor: StaffPrincipal,
        municipality_id: str,
        payload: ProvisionMunicipalityAdminRequest,
    ) -> ProvisionMunicipalityAdminResponse:
        profile = self.get_profile(municipality_id)
        if not profile.active:
            raise MunicipalityControlError(
                "Cannot provision an administrator for an inactive municipality."
            )
        stamped = _iso_now()
        user = StoredStaffUser(
            staffId=f"staff_{uuid4().hex[:12]}",
            username=payload.username,
            name=payload.name,
            email=payload.email,
            passwordHash=hash_password(payload.password),
            role="administrator",
            municipalityId=profile.municipality_id,
            departmentIds=None,
            active=True,
            sessionEpoch=0,
            createdAt=stamped,
            updatedAt=stamped,
        )
        try:
            created = self.staff_store().create(user)
        except StaffUsernameConflictError as exc:
            raise MunicipalityControlError("Username is already in use.") from exc
        self._audit.record_safe(
            action_type="STAFF_CREATED",
            actor=actor,
            target_staff_id=created.staff_id,
            summary=f"Provisioned municipality administrator for {profile.name}.",
            previous_value=None,
            new_value={
                "staffId": created.staff_id,
                "username": created.username,
                "role": created.role,
                "municipalityId": created.municipality_id,
            },
            created_at=stamped,
        )
        return ProvisionMunicipalityAdminResponse(
            staffId=created.staff_id,
            username=created.username,
            municipalityId=created.municipality_id or profile.municipality_id,
        )

    def preview(self, payload: RoutingPreviewRequest) -> RoutingPreviewResponse:
        from app.schemas.stored_ticket import StoredTicket as Ticket
        from app.schemas.ticket import ReportContact, ReportLocation

        fake = Ticket(
            ticketId="preview",
            ticketNumber="BG-0000-0",
            trackingCode="preview",
            description=payload.description or "Routing preview.",
            contact=ReportContact(name="Preview", phone="+96170000000", email=None),
            location=ReportLocation(
                latitude=payload.latitude,
                longitude=payload.longitude,
                addressText="Routing preview",
                source="MANUAL",
            ),
            imageObjectKey="preview/none.jpg",
            status="SUBMITTED",
            createdAt=_iso_now(),
        )
        decision = route_ticket_to_municipality(
            fake,
            category=payload.category,
            use_model=payload.use_model,
        )
        eligible_ids = set(decision.eligible_municipality_ids)
        if decision.municipality_id:
            eligible_ids.add(decision.municipality_id)
        profiles = [item for item in self.list_profiles() if item.municipality_id in eligible_ids]
        from app.schemas.municipality import MunicipalityResponse

        return RoutingPreviewResponse(
            decision=decision,
            eligible=[MunicipalityResponse.from_stored(item) for item in profiles],
        )

    def _park_active_tickets(
        self, actor: StaffPrincipal, profile: StoredMunicipality, stamped: str
    ) -> None:
        from app.services.municipalities.ticket_routing import unassign_ticket_for_deactivation

        for ticket in self.ticket_store().list():
            if ticket.municipality_id != profile.municipality_id:
                continue
            unassign_ticket_for_deactivation(
                ticket,
                actor=actor,
                profile=profile,
                stamped=stamped,
            )


municipality_control_service = MunicipalityControlService()
