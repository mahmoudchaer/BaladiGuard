"""Persisted staff audit history entries for ticket mutations (issues #143 / #181)."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.staff_user import StaffRole

AuditActionType = Literal[
    "STATUS_CHANGE",
    "CATEGORY_REVIEW",
    "DEPARTMENT_ASSIGN",
    "DUPLICATE_MERGE",
    "PUBLIC_CONTENT_UPDATE",
    "STAFF_COMMENT",
    "IMAGE_REDACTION_APPROVE",
    "IMAGE_REDACTION_REJECT",
    "IMAGE_REDACTION_REPROCESS",
    "IMAGE_REDACTION_MANUAL_BLUR",
    "WORKFORCE_ASSIGN",
    "WORK_ORDER_CREATE",
    "WORK_ORDER_ASSIGN",
    "WORK_ORDER_START",
    "WORK_ORDER_COMPLETE",
    "WORK_ORDER_CANCEL",
    "WORK_ORDER_EVIDENCE_ADD",
    "RESOLUTION_FEEDBACK_SUBMIT",
    "RESOLUTION_FEEDBACK_REVIEW",
]

AUDIT_ACTION_TYPES: tuple[AuditActionType, ...] = (
    "STATUS_CHANGE",
    "CATEGORY_REVIEW",
    "DEPARTMENT_ASSIGN",
    "DUPLICATE_MERGE",
    "PUBLIC_CONTENT_UPDATE",
    "STAFF_COMMENT",
    "IMAGE_REDACTION_APPROVE",
    "IMAGE_REDACTION_REJECT",
    "IMAGE_REDACTION_REPROCESS",
    "IMAGE_REDACTION_MANUAL_BLUR",
    "WORKFORCE_ASSIGN",
    "WORK_ORDER_CREATE",
    "WORK_ORDER_ASSIGN",
    "WORK_ORDER_START",
    "WORK_ORDER_COMPLETE",
    "WORK_ORDER_CANCEL",
    "WORK_ORDER_EVIDENCE_ADD",
    "RESOLUTION_FEEDBACK_SUBMIT",
    "RESOLUTION_FEEDBACK_REVIEW",
)


class StoredAuditHistory(BaseModel):
    audit_id: str = Field(alias="auditId")
    ticket_id: str = Field(alias="ticketId")
    action_type: AuditActionType = Field(alias="actionType")
    actor_id: str | None = Field(default=None, alias="actorId")
    # Verified staff role from the authenticated principal (issue #181).
    actor_role: StaffRole | None = Field(default=None, alias="actorRole")
    summary: str
    previous_value: str | None = Field(default=None, alias="previousValue")
    new_value: str | None = Field(default=None, alias="newValue")
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}
