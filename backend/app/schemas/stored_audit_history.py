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
]

AUDIT_ACTION_TYPES: tuple[AuditActionType, ...] = (
    "STATUS_CHANGE",
    "CATEGORY_REVIEW",
    "DEPARTMENT_ASSIGN",
    "DUPLICATE_MERGE",
    "PUBLIC_CONTENT_UPDATE",
    "STAFF_COMMENT",
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
