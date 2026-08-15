"""Maintenance work-order persistence and HTTP shapes (issue #247)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.ticket_status import TicketStatus
from app.schemas.workforce import AssignWorkforceRequest

WorkOrderState = Literal["QUEUED", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"]

WORK_ORDER_STATES: tuple[WorkOrderState, ...] = (
    "QUEUED",
    "ASSIGNED",
    "IN_PROGRESS",
    "COMPLETED",
    "CANCELLED",
)

ACTIVE_WORK_ORDER_STATES: frozenset[WorkOrderState] = frozenset(
    {"QUEUED", "ASSIGNED", "IN_PROGRESS"}
)

ALLOWED_WORK_ORDER_TRANSITIONS: dict[WorkOrderState, frozenset[WorkOrderState]] = {
    "QUEUED": frozenset({"ASSIGNED", "IN_PROGRESS", "CANCELLED"}),
    "ASSIGNED": frozenset({"IN_PROGRESS", "QUEUED", "CANCELLED"}),
    "IN_PROGRESS": frozenset({"COMPLETED", "ASSIGNED", "CANCELLED"}),
    "COMPLETED": frozenset(),
    "CANCELLED": frozenset(),
}

WORK_ORDER_STATE_LABELS: dict[WorkOrderState, str] = {
    "QUEUED": "Queued",
    "ASSIGNED": "Assigned",
    "IN_PROGRESS": "In progress",
    "COMPLETED": "Completed",
    "CANCELLED": "Cancelled",
}

WORK_ORDER_SUMMARY_MAX_LENGTH = 500


def is_active_work_order_state(state: WorkOrderState | str) -> bool:
    return state in ACTIVE_WORK_ORDER_STATES


def is_allowed_work_order_transition(
    current: WorkOrderState | str, requested: WorkOrderState | str
) -> bool:
    if current not in ALLOWED_WORK_ORDER_TRANSITIONS or requested not in WORK_ORDER_STATE_LABELS:
        return False
    return requested in ALLOWED_WORK_ORDER_TRANSITIONS[current]  # type: ignore[index]


class StoredWorkOrder(BaseModel):
    work_order_id: str = Field(alias="workOrderId")
    ticket_id: str = Field(alias="ticketId")
    municipality_id: str = Field(alias="municipalityId")
    department_id: str = Field(alias="departmentId")
    state: WorkOrderState
    summary: str
    assigned_worker_id: str | None = Field(default=None, alias="assignedWorkerId")
    assigned_team_id: str | None = Field(default=None, alias="assignedTeamId")
    created_at: str = Field(alias="createdAt")
    created_by: str = Field(alias="createdBy")
    updated_at: str = Field(alias="updatedAt")
    updated_by: str = Field(alias="updatedBy")
    started_at: str | None = Field(default=None, alias="startedAt")
    started_by: str | None = Field(default=None, alias="startedBy")
    completed_at: str | None = Field(default=None, alias="completedAt")
    completed_by: str | None = Field(default=None, alias="completedBy")
    cancelled_at: str | None = Field(default=None, alias="cancelledAt")
    cancelled_by: str | None = Field(default=None, alias="cancelledBy")
    cancel_reason_code: str | None = Field(default=None, alias="cancelReasonCode")
    completion_note: str | None = Field(default=None, alias="completionNote")
    cancel_note: str | None = Field(default=None, alias="cancelNote")

    model_config = {"populate_by_name": True}


class TicketOutcomeFields(BaseModel):
    """Staff-visible structured outcome. Private notes never appear on citizen reads."""

    resolution_reason_code: str | None = Field(default=None, alias="resolutionReasonCode")
    resolution_citizen_message: str | None = Field(default=None, alias="resolutionCitizenMessage")
    resolution_note: str | None = Field(default=None, alias="resolutionNote")
    resolved_at: str | None = Field(default=None, alias="resolvedAt")
    resolved_by: str | None = Field(default=None, alias="resolvedBy")
    closure_reason_code: str | None = Field(default=None, alias="closureReasonCode")
    closure_citizen_message: str | None = Field(default=None, alias="closureCitizenMessage")
    closure_note: str | None = Field(default=None, alias="closureNote")
    closed_at: str | None = Field(default=None, alias="closedAt")
    closed_by: str | None = Field(default=None, alias="closedBy")

    model_config = {"populate_by_name": True}


class CreateWorkOrderRequest(BaseModel):
    summary: str | None = Field(default=None, max_length=WORK_ORDER_SUMMARY_MAX_LENGTH)
    worker_id: str | None = Field(default=None, alias="workerId")
    team_id: str | None = Field(default=None, alias="teamId")

    model_config = {"populate_by_name": True}

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if len(trimmed) > WORK_ORDER_SUMMARY_MAX_LENGTH:
            raise ValueError(f"summary must be at most {WORK_ORDER_SUMMARY_MAX_LENGTH} characters.")
        return trimmed

    @model_validator(mode="after")
    def validate_assignee_xor(self) -> CreateWorkOrderRequest:
        if self.worker_id and self.team_id:
            raise ValueError("Assign either a worker or a team, not both.")
        return self


class CompleteWorkOrderRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)

    model_config = {"populate_by_name": True}

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class CancelWorkOrderRequest(BaseModel):
    reason_code: str = Field(alias="reasonCode")
    note: str | None = Field(default=None, max_length=500)

    model_config = {"populate_by_name": True}

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class WorkOrderResponse(BaseModel):
    work_order_id: str = Field(alias="workOrderId")
    ticket_id: str = Field(alias="ticketId")
    municipality_id: str = Field(alias="municipalityId")
    department_id: str = Field(alias="departmentId")
    state: WorkOrderState
    summary: str
    assigned_worker_id: str | None = Field(default=None, alias="assignedWorkerId")
    assigned_team_id: str | None = Field(default=None, alias="assignedTeamId")
    created_at: str = Field(alias="createdAt")
    created_by: str = Field(alias="createdBy")
    updated_at: str = Field(alias="updatedAt")
    updated_by: str = Field(alias="updatedBy")
    started_at: str | None = Field(default=None, alias="startedAt")
    started_by: str | None = Field(default=None, alias="startedBy")
    completed_at: str | None = Field(default=None, alias="completedAt")
    completed_by: str | None = Field(default=None, alias="completedBy")
    cancelled_at: str | None = Field(default=None, alias="cancelledAt")
    cancelled_by: str | None = Field(default=None, alias="cancelledBy")
    cancel_reason_code: str | None = Field(default=None, alias="cancelReasonCode")
    completion_note: str | None = Field(default=None, alias="completionNote")
    cancel_note: str | None = Field(default=None, alias="cancelNote")
    ticket_status: TicketStatus | None = Field(default=None, alias="ticketStatus")
    created: bool = False

    model_config = {"populate_by_name": True}

    @classmethod
    def from_work_order(
        cls,
        work_order: StoredWorkOrder,
        *,
        ticket_status: TicketStatus | None = None,
        created: bool = False,
    ) -> WorkOrderResponse:
        payload = work_order.model_dump(by_alias=True)
        payload["ticketStatus"] = ticket_status
        payload["created"] = created
        return cls.model_validate(payload)


class WorkOrderListResponse(BaseModel):
    items: list[WorkOrderResponse]
    active_work_order_id: str | None = Field(default=None, alias="activeWorkOrderId")

    model_config = {"populate_by_name": True}


AssignWorkOrderRequest = AssignWorkforceRequest
