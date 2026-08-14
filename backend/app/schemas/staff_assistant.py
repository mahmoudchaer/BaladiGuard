"""Public, grounded response models for the read-only staff assistant (#242 / #43)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class StaffAssistantQuery(BaseModel):
    question: str = Field(min_length=1, max_length=500)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question is required.")
        return value


class StaffAssistantTicketReference(BaseModel):
    ticket_id: str = Field(alias="ticketId")
    ticket_number: str = Field(alias="ticketNumber")
    status: str
    category: str
    priority: str | None = None
    sla_state: Literal["on_track", "due_soon", "overdue", "completed", "unavailable"] | None = (
        Field(default=None, alias="slaState")
    )
    municipality_id: str | None = Field(alias="municipalityId")
    department_id: str | None = Field(alias="departmentId")
    cell_id: str | None = Field(default=None, alias="cellId")
    duplicate_group_id: str | None = Field(default=None, alias="duplicateGroupId")

    model_config = {"populate_by_name": True}


class StaffAssistantAreaCluster(BaseModel):
    cell_id: str = Field(alias="cellId")
    south: float | None = None
    west: float | None = None
    north: float | None = None
    east: float | None = None
    label: str
    ticket_count: int = Field(alias="ticketCount", ge=0)
    distinct_report_count: int = Field(alias="distinctReportCount", ge=0)
    duplicate_group_count: int = Field(alias="duplicateGroupCount", ge=0)
    separate_report_count: int = Field(alias="separateReportCount", ge=0)
    categories: dict[str, int] = Field(default_factory=dict)
    ticket_ids: list[str] = Field(default_factory=list, alias="ticketIds")

    model_config = {"populate_by_name": True}


class StaffAssistantResponse(BaseModel):
    intent: Literal["high_priority_summary", "repeated_area_summary", "unsupported"]
    as_of: str = Field(alias="asOf")
    message: str
    count: int = Field(ge=0)
    categories: dict[str, int] = Field(default_factory=dict)
    statuses: dict[str, int] = Field(default_factory=dict)
    departments: dict[str, int] = Field(default_factory=dict)
    areas: dict[str, int] = Field(default_factory=dict)
    area_clusters: list[StaffAssistantAreaCluster] = Field(
        default_factory=list, alias="areaClusters"
    )
    unlocated_count: int = Field(default=0, alias="unlocatedCount", ge=0)
    incomplete_count: int = Field(default=0, alias="incompleteCount", ge=0)
    tickets: list[StaffAssistantTicketReference] = Field(default_factory=list)
    applied_filters: dict[str, str] = Field(default_factory=dict, alias="appliedFilters")

    model_config = {"populate_by_name": True}
