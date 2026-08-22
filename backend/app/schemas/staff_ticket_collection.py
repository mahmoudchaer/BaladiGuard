"""Lightweight staff ticket collection / map / aggregates schemas (issue #267)."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.content_safety import ContentSafetyStatus
from app.schemas.ticket_response import TicketPriority
from app.schemas.ticket_status import TicketStatus

AssignmentState = Literal["assigned", "unassigned"]


class TicketListLocation(BaseModel):
    latitude: float
    longitude: float
    address_text: str = Field(alias="addressText")

    model_config = {"populate_by_name": True}


class TicketListDepartment(BaseModel):
    department_id: str | None = Field(default=None, alias="departmentId")
    name: str | None = None

    model_config = {"populate_by_name": True}


class TicketListItemResponse(BaseModel):
    """Queue projection for staff list pages — no contact, history, or evidence URLs."""

    ticket_id: str = Field(alias="ticketId")
    ticket_number: str | None = Field(default=None, alias="ticketNumber")
    status: TicketStatus
    category: str
    priority: TicketPriority | None = None
    department_id: str | None = Field(default=None, alias="departmentId")
    department: TicketListDepartment | None = None
    summary: str
    created_at: str = Field(alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    municipality_id: str | None = Field(default=None, alias="municipalityId")
    assignment_state: AssignmentState = Field(alias="assignmentState")
    assigned_worker_id: str | None = Field(default=None, alias="assignedWorkerId")
    assigned_team_id: str | None = Field(default=None, alias="assignedTeamId")
    content_safety_status: ContentSafetyStatus | None = Field(
        default=None, alias="contentSafetyStatus"
    )
    location: TicketListLocation

    model_config = {"populate_by_name": True}


class TicketListPageResponse(BaseModel):
    items: list[TicketListItemResponse]
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    previous_cursor: str | None = Field(default=None, alias="previousCursor")
    limit: int = Field(ge=1, le=100)
    scanned_count: int | None = Field(default=None, alias="scannedCount")
    approximate_total: int | None = Field(default=None, alias="approximateTotal")
    freshness_hint_seconds: int = Field(default=30, alias="freshnessHintSeconds")

    model_config = {"populate_by_name": True}


class TicketMapMarkerResponse(BaseModel):
    ticket_id: str = Field(alias="ticketId")
    ticket_number: str | None = Field(default=None, alias="ticketNumber")
    status: TicketStatus
    priority: TicketPriority | None = None
    latitude: float
    longitude: float
    category: str

    model_config = {"populate_by_name": True}


class TicketMapClusterResponse(BaseModel):
    id: str
    latitude: float
    longitude: float
    count: int = Field(ge=1)

    model_config = {"populate_by_name": True}


class TicketMapViewportResponse(BaseModel):
    markers: list[TicketMapMarkerResponse]
    clusters: list[TicketMapClusterResponse]
    limit: int = Field(ge=1, le=500)
    truncated: bool
    zoom: float

    model_config = {"populate_by_name": True}


class TicketAggregatesResponse(BaseModel):
    open_count: int = Field(alias="openCount", ge=0)
    critical_count: int = Field(alias="criticalCount", ge=0)
    high_count: int = Field(alias="highCount", ge=0)
    unassigned_count: int = Field(alias="unassignedCount", ge=0)
    overdue_count: int = Field(alias="overdueCount", ge=0)
    queued_count: int = Field(default=0, alias="queuedCount", ge=0)
    assigned_count: int = Field(default=0, alias="assignedCount", ge=0)
    in_progress_count: int = Field(default=0, alias="inProgressCount", ge=0)
    due_soon_count: int = Field(default=0, alias="dueSoonCount", ge=0)
    completed_count: int = Field(default=0, alias="completedCount", ge=0)
    cancelled_count: int = Field(default=0, alias="cancelledCount", ge=0)
    workforce_unassigned_count: int = Field(default=0, alias="workforceUnassignedCount", ge=0)
    approximate: bool = False

    model_config = {"populate_by_name": True}
