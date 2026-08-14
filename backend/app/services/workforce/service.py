"""Municipality field workforce directory, assignment eligibility, and workload (#245)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.core.staff_auth import StaffPrincipal, staff_can_assign_department
from app.database.store_factory import get_workforce_store
from app.database.workforce_store import WorkforceStore
from app.schemas.stored_ticket import StoredTicket
from app.schemas.workforce import (
    AssignWorkforceRequest,
    StoredTeam,
    StoredWorker,
    TeamResponse,
    UpsertTeamRequest,
    UpsertWorkerRequest,
    WorkerResponse,
    WorkloadCounts,
    WorkloadResponse,
    WorkloadSubject,
    WorkloadTicketRef,
)
from app.services.complaints.sla import derive_ticket_sla
from app.services.complaints.ticket_list_filters import OPEN_TICKET_STATUSES
from app.services.routing import department_ids as catalog_department_ids
from app.services.staff.bootstrap import BEIRUT_MUNICIPALITY_ID

QUEUED_STATUSES = frozenset({"SUBMITTED", "UNDER_REVIEW"})
ASSIGNED_STATUSES = frozenset({"ASSIGNED"})
IN_PROGRESS_STATUSES = frozenset({"IN_PROGRESS"})
ASSIGNMENT_CLAIM_ATTEMPTS = 5


class WorkforceError(Exception):
    def __init__(
        self, message: str, *, status_code: int = 400, code: str = "VALIDATION_ERROR"
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def generate_worker_id() -> str:
    return f"wrk_{uuid4().hex}"


def generate_team_id() -> str:
    return f"team_{uuid4().hex}"


def _unique(values: list[str] | None) -> list[str]:
    if not values:
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        trimmed = value.strip()
        if not trimmed or trimmed in seen:
            continue
        seen.add(trimmed)
        ordered.append(trimmed)
    return ordered


def _validate_departments(department_ids: list[str]) -> list[str]:
    cleaned = _unique(department_ids)
    if not cleaned:
        raise WorkforceError("At least one department is required.")
    allowed = catalog_department_ids()
    unknown = [item for item in cleaned if item not in allowed]
    if unknown:
        raise WorkforceError(f"Unknown department: {unknown[0]}.")
    return cleaned


def resolve_municipality_scope(principal: StaffPrincipal, municipality_id: str | None) -> str:
    if principal.role != "administrator":
        if not principal.municipality_id:
            raise WorkforceError(
                "Staff municipality scope is required.",
                status_code=403,
                code="FORBIDDEN",
            )
        if municipality_id and municipality_id != principal.municipality_id:
            raise WorkforceError(
                "You cannot access another municipality's workforce.",
                status_code=403,
                code="FORBIDDEN",
            )
        return principal.municipality_id
    scoped = (municipality_id or "").strip() or BEIRUT_MUNICIPALITY_ID
    return scoped


def _require_admin(principal: StaffPrincipal) -> None:
    if principal.role != "administrator":
        raise WorkforceError(
            "Only administrators may manage the workforce directory.",
            status_code=403,
            code="FORBIDDEN",
        )


class WorkforceService:
    def __init__(self, store: WorkforceStore | None = None) -> None:
        self._store = store

    def store(self) -> WorkforceStore:
        return self._store or get_workforce_store()

    def list_workers(
        self, principal: StaffPrincipal, *, municipality_id: str | None
    ) -> list[WorkerResponse]:
        scoped = resolve_municipality_scope(principal, municipality_id)
        return [WorkerResponse.from_worker(item) for item in self.store().list_workers(scoped)]

    def list_teams(
        self, principal: StaffPrincipal, *, municipality_id: str | None
    ) -> list[TeamResponse]:
        scoped = resolve_municipality_scope(principal, municipality_id)
        return [TeamResponse.from_team(item) for item in self.store().list_teams(scoped)]

    def create_worker(
        self, principal: StaffPrincipal, payload: UpsertWorkerRequest
    ) -> WorkerResponse:
        _require_admin(principal)
        municipality_id = resolve_municipality_scope(principal, payload.municipality_id)
        if not payload.display_name or not payload.display_name.strip():
            raise WorkforceError("displayName is required.")
        departments = _validate_departments(payload.department_ids or [])
        now = _iso_now()
        worker = StoredWorker(
            workerId=generate_worker_id(),
            municipalityId=municipality_id,
            displayName=payload.display_name.strip(),
            departmentIds=departments,
            teamIds=_unique(payload.team_ids),
            active=True,
            createdAt=now,
            updatedAt=now,
        )
        self._assert_teams_compatible(worker)
        saved = self.store().save_worker(worker)
        self._sync_worker_teams(saved, previous_team_ids=[])
        return WorkerResponse.from_worker(self.store().get_worker(saved.worker_id) or saved)

    def update_worker(
        self, principal: StaffPrincipal, worker_id: str, payload: UpsertWorkerRequest
    ) -> WorkerResponse:
        _require_admin(principal)
        worker = self._require_worker(worker_id)
        previous_teams = list(worker.team_ids)
        updates: dict[str, object] = {"updated_at": _iso_now()}
        if payload.display_name is not None:
            updates["display_name"] = payload.display_name
        if payload.department_ids is not None:
            updates["department_ids"] = _validate_departments(payload.department_ids)
        if payload.team_ids is not None:
            updates["team_ids"] = _unique(payload.team_ids)
        if (
            payload.municipality_id is not None
            and payload.municipality_id != worker.municipality_id
        ):
            raise WorkforceError("municipalityId cannot be changed.")
        updated = worker.model_copy(update=updates)
        self._assert_teams_compatible(updated)
        saved = self.store().save_worker(updated)
        self._sync_worker_teams(saved, previous_team_ids=previous_teams)
        return WorkerResponse.from_worker(self.store().get_worker(saved.worker_id) or saved)

    def set_worker_active(
        self, principal: StaffPrincipal, worker_id: str, *, active: bool
    ) -> WorkerResponse:
        _require_admin(principal)
        worker = self._require_worker(worker_id)
        saved = self.store().save_worker(
            worker.model_copy(update={"active": active, "updated_at": _iso_now()})
        )
        return WorkerResponse.from_worker(saved)

    def create_team(self, principal: StaffPrincipal, payload: UpsertTeamRequest) -> TeamResponse:
        _require_admin(principal)
        municipality_id = resolve_municipality_scope(principal, payload.municipality_id)
        if not payload.display_name or not payload.display_name.strip():
            raise WorkforceError("displayName is required.")
        departments = _validate_departments(payload.department_ids or [])
        now = _iso_now()
        team = StoredTeam(
            teamId=generate_team_id(),
            municipalityId=municipality_id,
            displayName=payload.display_name.strip(),
            departmentIds=departments,
            workerIds=_unique(payload.worker_ids),
            active=True,
            createdAt=now,
            updatedAt=now,
        )
        self._assert_workers_compatible(team)
        saved = self.store().save_team(team)
        self._sync_team_workers(saved, previous_worker_ids=[])
        return TeamResponse.from_team(self.store().get_team(saved.team_id) or saved)

    def update_team(
        self, principal: StaffPrincipal, team_id: str, payload: UpsertTeamRequest
    ) -> TeamResponse:
        _require_admin(principal)
        team = self._require_team(team_id)
        previous_workers = list(team.worker_ids)
        updates: dict[str, object] = {"updated_at": _iso_now()}
        if payload.display_name is not None:
            updates["display_name"] = payload.display_name
        if payload.department_ids is not None:
            updates["department_ids"] = _validate_departments(payload.department_ids)
        if payload.worker_ids is not None:
            updates["worker_ids"] = _unique(payload.worker_ids)
        if payload.municipality_id is not None and payload.municipality_id != team.municipality_id:
            raise WorkforceError("municipalityId cannot be changed.")
        updated = team.model_copy(update=updates)
        self._assert_workers_compatible(updated)
        saved = self.store().save_team(updated)
        self._sync_team_workers(saved, previous_worker_ids=previous_workers)
        return TeamResponse.from_team(self.store().get_team(saved.team_id) or saved)

    def set_team_active(
        self, principal: StaffPrincipal, team_id: str, *, active: bool
    ) -> TeamResponse:
        _require_admin(principal)
        team = self._require_team(team_id)
        saved = self.store().save_team(
            team.model_copy(update={"active": active, "updated_at": _iso_now()})
        )
        return TeamResponse.from_team(saved)

    def resolve_ticket_assignment(
        self,
        principal: StaffPrincipal,
        ticket: StoredTicket,
        payload: AssignWorkforceRequest,
    ) -> tuple[str | None, str | None]:
        worker_id = (payload.worker_id or "").strip() or None
        team_id = (payload.team_id or "").strip() or None
        if payload.clear:
            if worker_id or team_id:
                raise WorkforceError("clear cannot be combined with a worker or team assignment.")
            return None, None
        if worker_id and team_id:
            raise WorkforceError("Assign either a worker or a team, not both.")
        if not worker_id and not team_id:
            raise WorkforceError("Provide workerId, teamId, or clear=true.")

        if worker_id:
            worker = self.store().get_worker(worker_id)
            if worker is None:
                raise WorkforceError(
                    "Worker was not found.", status_code=404, code="WORKER_NOT_FOUND"
                )
            self._assert_assignee_eligible(
                principal,
                ticket,
                worker.municipality_id,
                worker.department_ids,
                worker.active,
                "worker",
            )
            return worker.worker_id, None

        team = self.store().get_team(team_id or "")
        if team is None:
            raise WorkforceError("Team was not found.", status_code=404, code="TEAM_NOT_FOUND")
        self._assert_assignee_eligible(
            principal, ticket, team.municipality_id, team.department_ids, team.active, "team"
        )
        return None, team.team_id

    def claim_ticket_assignment(
        self,
        principal: StaffPrincipal,
        ticket: StoredTicket,
        payload: AssignWorkforceRequest,
    ) -> tuple[str | None, str | None]:
        store = self.store()
        for _ in range(ASSIGNMENT_CLAIM_ATTEMPTS):
            worker_id, team_id = self.resolve_ticket_assignment(principal, ticket, payload)
            if worker_id is None and team_id is None:
                return None, None
            if worker_id is not None:
                worker = store.get_worker(worker_id)
                if worker is None:
                    raise WorkforceError(
                        "Worker was not found.", status_code=404, code="WORKER_NOT_FOUND"
                    )
                if store.claim_worker(worker_id, worker.updated_at, ticket.department_id):
                    return worker_id, None
                continue
            team = store.get_team(team_id or "")
            if team is None:
                raise WorkforceError("Team was not found.", status_code=404, code="TEAM_NOT_FOUND")
            if store.claim_team(team.team_id, team.updated_at, ticket.department_id):
                return None, team.team_id
        raise WorkforceError(
            "Assignment could not be completed because the assignee changed. Retry.",
            status_code=409,
            code="CONFLICT",
        )

    def workload(
        self, principal: StaffPrincipal, *, municipality_id: str | None
    ) -> WorkloadResponse:
        scoped = resolve_municipality_scope(principal, municipality_id)
        workers = self.store().list_workers(scoped)
        teams = self.store().list_teams(scoped)
        from app.services.complaints.ticket_service import ticket_service

        collected = ticket_service.collect_all_staff_tickets(principal)
        tickets = [ticket for ticket in collected if ticket.municipality_id in {None, scoped}]

        unassigned_open = [
            ticket
            for ticket in tickets
            if ticket.status in OPEN_TICKET_STATUSES
            and not ticket.assigned_worker_id
            and not ticket.assigned_team_id
        ]
        worker_subjects = [
            self._subject_for_worker(
                worker,
                [ticket for ticket in tickets if ticket.assigned_worker_id == worker.worker_id],
            )
            for worker in workers
        ]
        team_subjects = [
            self._subject_for_team(
                team,
                [ticket for ticket in tickets if ticket.assigned_team_id == team.team_id],
            )
            for team in teams
        ]
        return WorkloadResponse(
            municipalityId=scoped,
            unassigned=_counts_for(unassigned_open),
            unassignedTickets=_ticket_refs(unassigned_open),
            workers=worker_subjects,
            teams=team_subjects,
        )

    def _require_worker(self, worker_id: str) -> StoredWorker:
        worker = self.store().get_worker(worker_id)
        if worker is None:
            raise WorkforceError("Worker was not found.", status_code=404, code="WORKER_NOT_FOUND")
        return worker

    def _require_team(self, team_id: str) -> StoredTeam:
        team = self.store().get_team(team_id)
        if team is None:
            raise WorkforceError("Team was not found.", status_code=404, code="TEAM_NOT_FOUND")
        return team

    def _assert_teams_compatible(self, worker: StoredWorker) -> None:
        for team_id in worker.team_ids:
            team = self.store().get_team(team_id)
            if team is None:
                raise WorkforceError("Team was not found.", status_code=404, code="TEAM_NOT_FOUND")
            if team.municipality_id != worker.municipality_id:
                raise WorkforceError("Workers and teams must belong to the same municipality.")

    def _assert_workers_compatible(self, team: StoredTeam) -> None:
        for worker_id in team.worker_ids:
            worker = self.store().get_worker(worker_id)
            if worker is None:
                raise WorkforceError(
                    "Worker was not found.", status_code=404, code="WORKER_NOT_FOUND"
                )
            if worker.municipality_id != team.municipality_id:
                raise WorkforceError("Workers and teams must belong to the same municipality.")

    def _sync_worker_teams(self, worker: StoredWorker, *, previous_team_ids: list[str]) -> None:
        desired = set(worker.team_ids)
        previous = set(previous_team_ids)
        for team_id in previous | desired:
            team = self.store().get_team(team_id)
            if team is None:
                continue
            members = [item for item in team.worker_ids if item != worker.worker_id]
            if team_id in desired:
                members.append(worker.worker_id)
            if members != team.worker_ids:
                self.store().save_team(
                    team.model_copy(update={"worker_ids": members, "updated_at": _iso_now()})
                )

    def _sync_team_workers(self, team: StoredTeam, *, previous_worker_ids: list[str]) -> None:
        desired = set(team.worker_ids)
        previous = set(previous_worker_ids)
        for worker_id in previous | desired:
            worker = self.store().get_worker(worker_id)
            if worker is None:
                continue
            memberships = [item for item in worker.team_ids if item != team.team_id]
            if worker_id in desired:
                memberships.append(team.team_id)
            if memberships != worker.team_ids:
                self.store().save_worker(
                    worker.model_copy(update={"team_ids": memberships, "updated_at": _iso_now()})
                )

    def _assert_assignee_eligible(
        self,
        principal: StaffPrincipal,
        ticket: StoredTicket,
        assignee_municipality: str,
        assignee_departments: list[str],
        active: bool,
        kind: str,
    ) -> None:
        if not active:
            raise WorkforceError(f"Inactive {kind}s cannot receive new assignments.")
        ticket_municipality = ticket.municipality_id
        if ticket_municipality and ticket_municipality != assignee_municipality:
            raise WorkforceError("Assignee municipality does not match the ticket.")
        if principal.role != "administrator" and principal.municipality_id != assignee_municipality:
            raise WorkforceError(
                "You cannot assign workforce outside your municipality.",
                status_code=403,
                code="FORBIDDEN",
            )
        if ticket.department_id:
            if ticket.department_id not in assignee_departments:
                raise WorkforceError("Assignee is not a member of the ticket department.")
            if not staff_can_assign_department(principal, ticket.department_id):
                raise WorkforceError(
                    "You do not have permission to assign this department.",
                    status_code=403,
                    code="FORBIDDEN",
                )

    def _subject_for_worker(
        self, worker: StoredWorker, tickets: list[StoredTicket]
    ) -> WorkloadSubject:
        open_tickets = [ticket for ticket in tickets if ticket.status in OPEN_TICKET_STATUSES]
        return WorkloadSubject(
            id=worker.worker_id,
            kind="worker",
            displayName=worker.display_name,
            departmentIds=worker.department_ids,
            active=worker.active,
            counts=_counts_for(open_tickets),
            tickets=_ticket_refs(open_tickets),
        )

    def _subject_for_team(self, team: StoredTeam, tickets: list[StoredTicket]) -> WorkloadSubject:
        open_tickets = [ticket for ticket in tickets if ticket.status in OPEN_TICKET_STATUSES]
        return WorkloadSubject(
            id=team.team_id,
            kind="team",
            displayName=team.display_name,
            departmentIds=team.department_ids,
            active=team.active,
            counts=_counts_for(open_tickets),
            tickets=_ticket_refs(open_tickets),
        )


def _counts_for(tickets: list[StoredTicket]) -> WorkloadCounts:
    queued = sum(1 for ticket in tickets if ticket.status in QUEUED_STATUSES)
    assigned = sum(1 for ticket in tickets if ticket.status in ASSIGNED_STATUSES)
    in_progress = sum(1 for ticket in tickets if ticket.status in IN_PROGRESS_STATUSES)
    due_soon = 0
    overdue = 0
    for ticket in tickets:
        state = derive_ticket_sla(ticket).state
        if state == "due_soon":
            due_soon += 1
        elif state == "overdue":
            overdue += 1
    return WorkloadCounts(
        queued=queued,
        assigned=assigned,
        inProgress=in_progress,
        dueSoon=due_soon,
        overdue=overdue,
    )


def _ticket_refs(tickets: list[StoredTicket]) -> list[WorkloadTicketRef]:
    refs: list[WorkloadTicketRef] = []
    for ticket in sorted(tickets, key=lambda item: item.created_at, reverse=True):
        refs.append(
            WorkloadTicketRef(
                ticketId=ticket.ticket_id,
                ticketNumber=ticket.ticket_number,
                status=ticket.status,
                departmentId=ticket.department_id,
                slaState=derive_ticket_sla(ticket).state,
            )
        )
    return refs


workforce_service = WorkforceService()
