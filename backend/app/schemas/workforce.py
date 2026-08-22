"""Municipality field workforce directory (issue #245). Separate from staff login accounts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

BoundedId = Annotated[str, Field(min_length=1, max_length=80)]

WorkforceAssigneeKind = Literal["worker", "team"]


class StoredWorker(BaseModel):
    worker_id: str = Field(alias="workerId")
    municipality_id: str = Field(alias="municipalityId")
    display_name: str = Field(alias="displayName")
    department_ids: list[BoundedId] = Field(alias="departmentIds", max_length=40)
    team_ids: list[BoundedId] = Field(default_factory=list, alias="teamIds", max_length=40)
    active: bool = True
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed or len(trimmed) > 120:
            raise ValueError("displayName must be 1–120 characters.")
        return trimmed


class StoredTeam(BaseModel):
    team_id: str = Field(alias="teamId")
    municipality_id: str = Field(alias="municipalityId")
    display_name: str = Field(alias="displayName")
    department_ids: list[BoundedId] = Field(alias="departmentIds", max_length=40)
    worker_ids: list[BoundedId] = Field(default_factory=list, alias="workerIds", max_length=80)
    lead_worker_id: BoundedId | None = Field(default=None, alias="leadWorkerId")
    active: bool = True
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed or len(trimmed) > 120:
            raise ValueError("displayName must be 1–120 characters.")
        return trimmed


class WorkerResponse(BaseModel):
    worker_id: str = Field(alias="workerId")
    municipality_id: str = Field(alias="municipalityId")
    display_name: str = Field(alias="displayName")
    department_ids: list[str] = Field(alias="departmentIds")
    team_ids: list[str] = Field(alias="teamIds")
    active: bool
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_worker(cls, worker: StoredWorker) -> WorkerResponse:
        return cls.model_validate(worker.model_dump(by_alias=True))


class TeamResponse(BaseModel):
    team_id: str = Field(alias="teamId")
    municipality_id: str = Field(alias="municipalityId")
    display_name: str = Field(alias="displayName")
    department_ids: list[str] = Field(alias="departmentIds")
    worker_ids: list[str] = Field(alias="workerIds")
    lead_worker_id: str | None = Field(default=None, alias="leadWorkerId")
    active: bool
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_team(cls, team: StoredTeam) -> TeamResponse:
        return cls.model_validate(team.model_dump(by_alias=True))


class UpsertWorkerRequest(BaseModel):
    municipality_id: str | None = Field(default=None, alias="municipalityId", max_length=80)
    display_name: str | None = Field(default=None, alias="displayName")
    department_ids: list[BoundedId] | None = Field(
        default=None, alias="departmentIds", max_length=40
    )
    team_ids: list[BoundedId] | None = Field(default=None, alias="teamIds", max_length=40)

    model_config = {"populate_by_name": True}

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed or len(trimmed) > 120:
            raise ValueError("displayName must be 1–120 characters.")
        return trimmed


class UpsertTeamRequest(BaseModel):
    municipality_id: str | None = Field(default=None, alias="municipalityId", max_length=80)
    display_name: str | None = Field(default=None, alias="displayName")
    department_ids: list[BoundedId] | None = Field(
        default=None, alias="departmentIds", max_length=40
    )
    worker_ids: list[BoundedId] | None = Field(default=None, alias="workerIds", max_length=80)
    lead_worker_id: BoundedId | None = Field(default=None, alias="leadWorkerId")

    model_config = {"populate_by_name": True}

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed or len(trimmed) > 120:
            raise ValueError("displayName must be 1–120 characters.")
        return trimmed


class AssignWorkforceRequest(BaseModel):
    worker_id: str | None = Field(default=None, alias="workerId")
    team_id: str | None = Field(default=None, alias="teamId")
    clear: bool = False

    model_config = {"populate_by_name": True}


class WorkloadCounts(BaseModel):
    queued: int = 0
    assigned: int = 0
    in_progress: int = Field(default=0, alias="inProgress")
    due_soon: int = Field(default=0, alias="dueSoon")
    overdue: int = 0
    completed: int = 0
    cancelled: int = 0

    model_config = {"populate_by_name": True}


class WorkloadTicketRef(BaseModel):
    ticket_id: str = Field(alias="ticketId")
    ticket_number: str = Field(alias="ticketNumber")
    status: str
    department_id: str | None = Field(default=None, alias="departmentId")
    sla_state: str | None = Field(default=None, alias="slaState")

    model_config = {"populate_by_name": True}


class WorkloadSubject(BaseModel):
    id: str
    kind: WorkforceAssigneeKind
    display_name: str = Field(alias="displayName")
    department_ids: list[str] = Field(alias="departmentIds")
    active: bool
    counts: WorkloadCounts
    tickets: list[WorkloadTicketRef] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class WorkloadResponse(BaseModel):
    municipality_id: str = Field(alias="municipalityId")
    unassigned: WorkloadCounts
    unassigned_tickets: list[WorkloadTicketRef] = Field(
        default_factory=list, alias="unassignedTickets"
    )
    workers: list[WorkloadSubject] = Field(default_factory=list)
    teams: list[WorkloadSubject] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
