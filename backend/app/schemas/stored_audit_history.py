"""Persisted staff audit history entries for ticket mutations (issue #143)."""

from typing import Literal

from pydantic import BaseModel, Field

AuditActionType = Literal[
    "STATUS_CHANGE",
    "CATEGORY_REVIEW",
    "DEPARTMENT_ASSIGN",
    "DUPLICATE_MERGE",
]

AUDIT_ACTION_TYPES: tuple[AuditActionType, ...] = (
    "STATUS_CHANGE",
    "CATEGORY_REVIEW",
    "DEPARTMENT_ASSIGN",
    "DUPLICATE_MERGE",
)


class StoredAuditHistory(BaseModel):
    audit_id: str = Field(alias="auditId")
    ticket_id: str = Field(alias="ticketId")
    action_type: AuditActionType = Field(alias="actionType")
    actor_id: str | None = Field(default=None, alias="actorId")
    summary: str
    previous_value: str | None = Field(default=None, alias="previousValue")
    new_value: str | None = Field(default=None, alias="newValue")
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}
