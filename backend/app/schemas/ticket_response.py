from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.ticket import ReportLocation

TicketStatus = Literal[
    "SUBMITTED",
    "UNDER_REVIEW",
    "ASSIGNED",
    "IN_PROGRESS",
    "RESOLVED",
]
TicketPriority = Literal["low", "medium", "high"]


class TicketImageReference(BaseModel):
    object_key: str = Field(alias="objectKey")
    url: str | None = None
    content_type: str | None = Field(default=None, alias="contentType")
    created_at: str | None = Field(default=None, alias="createdAt")

    model_config = {"populate_by_name": True}


class TicketDepartment(BaseModel):
    department_id: str | None = Field(default=None, alias="departmentId")
    name: str | None = None

    model_config = {"populate_by_name": True}


class TicketAiFields(BaseModel):
    cleaned_description: str | None = Field(default=None, alias="cleanedDescription")
    suggested_category: str | None = Field(default=None, alias="suggestedCategory")
    urgency_reason: str | None = Field(default=None, alias="urgencyReason")
    summary: str | None = None

    model_config = {"populate_by_name": True}


class TicketStatusHistoryEntry(BaseModel):
    status: TicketStatus
    changed_at: str = Field(alias="changedAt")
    changed_by: str | None = Field(default=None, alias="changedBy")
    note: str | None = None

    model_config = {"populate_by_name": True}


class TicketDuplicateReference(BaseModel):
    duplicate_group_id: str = Field(alias="duplicateGroupId")
    ticket_ids: list[str] | None = Field(default=None, alias="ticketIds")
    canonical_ticket_id: str | None = Field(default=None, alias="canonicalTicketId")

    model_config = {"populate_by_name": True}


class TicketResponse(BaseModel):
    """Shared ticket read shape returned by staff dashboard and ticket read APIs."""

    ticket_id: str = Field(alias="ticketId")
    ticket_number: str | None = Field(default=None, alias="ticketNumber")
    description: str
    category: str
    priority: TicketPriority | None
    status: TicketStatus
    location: ReportLocation
    image_references: list[TicketImageReference] = Field(alias="imageReferences")
    department: TicketDepartment | None
    created_at: str = Field(alias="createdAt")
    updated_at: str | None = Field(alias="updatedAt")
    ai: TicketAiFields | None = None
    status_history: list[TicketStatusHistoryEntry] | None = Field(
        default=None,
        alias="statusHistory",
    )
    duplicate_group: TicketDuplicateReference | None = Field(
        default=None,
        alias="duplicateGroup",
    )

    model_config = {"populate_by_name": True}
