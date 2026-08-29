"""Ticket municipality assignment, claim, reject, and override (issue #322)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.staff_auth import StaffPrincipal, staff_can_access_ticket
from app.database.store_factory import get_municipality_store, get_ticket_store
from app.schemas.municipality import (
    MunicipalityClaimRequest,
    MunicipalityOverrideRequest,
    MunicipalityRejectRequest,
)
from app.schemas.stored_municipality import (
    MunicipalityRoutingDecision,
    MunicipalityRoutingProvenance,
    StoredMunicipality,
)
from app.schemas.stored_ticket import StoredTicket
from app.services.routing.department_map import suggest_department_id
from app.services.routing.geo import municipality_covers_point
from app.services.routing.municipality_router import (
    eligible_municipalities,
    service_domain_for_category,
)

HISTORY_CAP = 20
OPEN_STATUSES = {"SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS"}


class MunicipalityRoutingError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        code: str = "VALIDATION_ERROR",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def snapshot_routing(
    ticket: StoredTicket,
    *,
    actor: StaffPrincipal | None,
    note: str | None,
    stamped: str,
) -> MunicipalityRoutingProvenance:
    raw = ticket.municipality_routing
    if isinstance(raw, dict):
        decision = MunicipalityRoutingDecision.model_validate(raw)
    elif raw is None:
        decision = MunicipalityRoutingDecision(
            status=ticket.municipality_routing_status or "unassigned",
            municipalityId=ticket.municipality_id,
            method="fallback",
            reasonCode="ROUTE_SNAPSHOT",
            reason="Prior routing state.",
        )
    else:
        decision = raw
    return MunicipalityRoutingProvenance(
        **decision.model_dump(),
        actorId=None if actor is None else actor.staff_id,
        actorRole=None if actor is None else actor.role,
        note=note,
        recordedAt=stamped,
    )


def append_routing_history(
    ticket: StoredTicket, entry: MunicipalityRoutingProvenance
) -> list[MunicipalityRoutingProvenance]:
    history = [
        item
        if isinstance(item, MunicipalityRoutingProvenance)
        else MunicipalityRoutingProvenance.model_validate(item)
        for item in ticket.municipality_routing_history
    ]
    history.append(entry)
    return history[-HISTORY_CAP:]


def apply_routing_decision(
    ticket: StoredTicket,
    decision: MunicipalityRoutingDecision,
    *,
    actor: StaffPrincipal | None = None,
    note: str | None = None,
    stamped: str | None = None,
    category: str | None = None,
) -> dict[str, object]:
    recorded = stamped or _iso_now()
    history_entry = snapshot_routing(ticket, actor=actor, note=note, stamped=recorded)
    assigned_id = decision.municipality_id if decision.status == "assigned" else None
    fields: dict[str, object] = {
        "municipality_id": assigned_id,
        "municipality_routing_status": decision.status,
        "municipality_routing": decision.model_dump(by_alias=True, exclude_none=True),
        "municipality_routing_history": [
            item.model_dump(by_alias=True, exclude_none=True)
            for item in append_routing_history(ticket, history_entry)
        ],
        "updated_at": recorded,
    }
    if assigned_id:
        resolved_category = (
            category or ticket.final_category or ticket.ai_suggested_category or ticket.category
        )
        if resolved_category == "PENDING_CLASSIFICATION":
            resolved_category = None
        suggested = suggest_department_id(
            category_id=resolved_category, municipality_id=assigned_id
        )
        if suggested:
            fields["suggested_department_id"] = suggested
            auto_department = (
                ticket.department_id is None
                or ticket.department_id == ticket.suggested_department_id
            )
            if auto_department:
                fields["department_id"] = suggested
    else:
        fields["department_id"] = None
        fields["suggested_department_id"] = None
    return fields


def unassign_ticket_for_deactivation(
    ticket: StoredTicket,
    *,
    actor: StaffPrincipal,
    profile: StoredMunicipality,
    stamped: str,
) -> StoredTicket | None:
    if ticket.status not in OPEN_STATUSES or ticket.municipality_id != profile.municipality_id:
        return None
    decision = MunicipalityRoutingDecision(
        status="unassigned",
        method="deactivation",
        reasonCode="ROUTE_INACTIVE",
        reason=f"Municipality {profile.name} was deactivated.",
        profileVersion=profile.profile_version,
        eligibleMunicipalityIds=[],
    )
    fields = apply_routing_decision(ticket, decision, actor=actor, stamped=stamped)
    return get_ticket_store().patch_fields(
        ticket.ticket_id,
        fields,
        expected_municipality_id=profile.municipality_id,
    )


def _require_ticket(ticket_id: str, principal: StaffPrincipal) -> StoredTicket:
    from app.services.complaints.ticket_service import TicketNotFoundError

    store = get_ticket_store()
    ticket = store.get(ticket_id)
    if ticket is None:
        ticket = store.get_by_ticket_number(ticket_id)
    if ticket is None:
        raise TicketNotFoundError(ticket_id)
    if principal.role == "developer_operator":
        return ticket
    if not staff_can_access_ticket(principal, ticket) and not _is_unassigned(ticket):
        raise TicketNotFoundError(ticket_id)
    return ticket


def _is_unassigned(ticket: StoredTicket) -> bool:
    if ticket.municipality_id:
        return False
    return ticket.municipality_routing_status in {None, "unassigned", "pending"}


def claim_ticket(
    ticket_id: str, principal: StaffPrincipal, payload: MunicipalityClaimRequest
) -> StoredTicket:
    if principal.role == "developer_operator":
        raise MunicipalityRoutingError(
            "Use override to reassign as a developer operator.",
            status_code=403,
        )
    if not principal.municipality_id:
        raise MunicipalityRoutingError(
            "Staff municipality scope is required to claim.",
            status_code=403,
        )
    ticket = _require_ticket(ticket_id, principal)
    if not _is_unassigned(ticket):
        raise MunicipalityRoutingError(
            "Ticket is already assigned.",
            status_code=409,
            code="ROUTING_CONFLICT",
        )

    profile = get_municipality_store().get(principal.municipality_id)
    if profile is None or not profile.active:
        raise MunicipalityRoutingError("Your municipality is not active.")
    category = ticket.final_category or ticket.ai_suggested_category or ticket.category
    eligible = eligible_municipalities(
        [profile],
        latitude=ticket.location.latitude,
        longitude=ticket.location.longitude,
        category=category if category != "PENDING_CLASSIFICATION" else None,
    )
    if not eligible:
        domain = service_domain_for_category(category)
        covers = municipality_covers_point(
            profile, latitude=ticket.location.latitude, longitude=ticket.location.longitude
        )
        if not covers or (domain and domain not in profile.service_domains):
            raise MunicipalityRoutingError(
                "This ticket is outside your geography or service mandate.",
                status_code=409,
                code="CLAIM_NOT_ELIGIBLE",
            )
    decision = MunicipalityRoutingDecision(
        status="assigned",
        municipalityId=profile.municipality_id,
        suggestedMunicipalityId=profile.municipality_id,
        confidence=1.0,
        method="staff_claim",
        reasonCode=payload.reason_code,
        reason="Municipality claimed this unassigned ticket.",
        profileVersion=profile.profile_version,
        eligibleMunicipalityIds=[profile.municipality_id],
    )
    fields = apply_routing_decision(ticket, decision, actor=principal, note=payload.note)
    updated = get_ticket_store().patch_fields(
        ticket.ticket_id,
        fields,
        expected_municipality_id=None,
        expected_values={"municipality_id": None},
    )
    if updated is None:
        raise MunicipalityRoutingError(
            "Another municipality already claimed this ticket.",
            status_code=409,
            code="ROUTING_CONFLICT",
        )
    _record_audit(
        updated,
        principal,
        "MUNICIPALITY_CLAIM",
        ticket.municipality_id,
        updated.municipality_id,
    )
    return updated


def reject_ticket(
    ticket_id: str, principal: StaffPrincipal, payload: MunicipalityRejectRequest
) -> StoredTicket:
    ticket = _require_ticket(ticket_id, principal)
    if principal.role != "developer_operator":
        from app.services.complaints.ticket_service import TicketNotFoundError

        if ticket.municipality_id != principal.municipality_id:
            raise TicketNotFoundError(ticket_id)
    if not ticket.municipality_id:
        raise MunicipalityRoutingError("Ticket is not assigned.")
    previous = ticket.municipality_id
    decision = MunicipalityRoutingDecision(
        status="unassigned",
        method="staff_reject",
        reasonCode=payload.reason_code,
        reason="Municipality rejected ownership.",
        eligibleMunicipalityIds=[],
        profileVersion=(
            ticket.municipality_routing.profile_version if ticket.municipality_routing else None
        ),
    )
    fields = apply_routing_decision(ticket, decision, actor=principal, note=payload.note)
    updated = get_ticket_store().patch_fields(
        ticket.ticket_id,
        fields,
        expected_municipality_id=previous,
    )
    if updated is None:
        raise MunicipalityRoutingError(
            "Ticket assignment changed.", status_code=409, code="ROUTING_CONFLICT"
        )
    _record_audit(updated, principal, "MUNICIPALITY_REJECT", previous, None)
    return updated


def override_ticket(
    ticket_id: str, principal: StaffPrincipal, payload: MunicipalityOverrideRequest
) -> StoredTicket:
    if principal.role != "developer_operator":
        raise MunicipalityRoutingError(
            "Only developer operators may override routing.",
            status_code=403,
        )
    from app.services.complaints.ticket_service import TicketNotFoundError

    ticket = _require_ticket(ticket_id, principal)
    previous = ticket.municipality_id
    assigned_id = payload.municipality_id
    if assigned_id:
        from app.database.store_factory import get_municipality_store

        profile = get_municipality_store().get(assigned_id)
        if profile is None:
            raise MunicipalityRoutingError("Target municipality was not found.", status_code=404)
        decision = MunicipalityRoutingDecision(
            status="assigned",
            municipalityId=profile.municipality_id,
            suggestedMunicipalityId=profile.municipality_id,
            confidence=1.0,
            method="operator_override",
            reasonCode=payload.reason_code,
            reason="Developer operator reassigned the ticket.",
            profileVersion=profile.profile_version,
            eligibleMunicipalityIds=[profile.municipality_id],
        )
    else:
        decision = MunicipalityRoutingDecision(
            status="unassigned",
            method="operator_override",
            reasonCode=payload.reason_code,
            reason="Developer operator returned the ticket to the unassigned queue.",
        )
    fields = apply_routing_decision(ticket, decision, actor=principal, note=payload.note)
    updated = get_ticket_store().patch_fields(ticket.ticket_id, fields)
    if updated is None:
        raise TicketNotFoundError(ticket_id)
    _record_audit(updated, principal, "MUNICIPALITY_OVERRIDE", previous, updated.municipality_id)
    from app.services.rewards.observe import observe_ticket_rewards

    observe_ticket_rewards(updated)
    return updated


def _record_audit(
    ticket: StoredTicket,
    principal: StaffPrincipal,
    action: str,
    previous: str | None,
    new: str | None,
) -> None:
    try:
        from app.services.complaints.ticket_service import ticket_service

        ticket_service._record_audit_history(
            ticket_id=ticket.ticket_id,
            action_type=action,  # type: ignore[arg-type]
            actor_id=principal.staff_id,
            actor_role=principal.role,
            summary=f"Municipality routing {action.split('_')[-1].lower()}.",
            previous_value=previous,
            new_value=new,
            created_at=ticket.updated_at or _iso_now(),
        )
    except Exception:
        return
