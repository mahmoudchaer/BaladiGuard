"""Persisted account-audit entries for staff/admin mutations (issue #181).

These are not ticket-scoped. Payloads must never include passwords, hashes,
tokens, reset codes, or unnecessary citizen data.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.staff_user import StaffRole

AccountAuditActionType = Literal[
    "STAFF_CREATED",
    "STAFF_ROLE_CHANGED",
    "STAFF_SCOPE_CHANGED",
    "STAFF_DEACTIVATED",
    "STAFF_REACTIVATED",
    "STAFF_PASSWORD_RESET_COMPLETED",
    "STAFF_SESSION_REVOKED",
]

ACCOUNT_AUDIT_ACTION_TYPES: tuple[AccountAuditActionType, ...] = (
    "STAFF_CREATED",
    "STAFF_ROLE_CHANGED",
    "STAFF_SCOPE_CHANGED",
    "STAFF_DEACTIVATED",
    "STAFF_REACTIVATED",
    "STAFF_PASSWORD_RESET_COMPLETED",
    "STAFF_SESSION_REVOKED",
)


class StoredAccountAudit(BaseModel):
    audit_id: str = Field(alias="auditId")
    action_type: AccountAuditActionType = Field(alias="actionType")
    actor_id: str | None = Field(default=None, alias="actorId")
    actor_role: StaffRole | None = Field(default=None, alias="actorRole")
    target_staff_id: str = Field(alias="targetStaffId")
    summary: str
    previous_value: str | None = Field(default=None, alias="previousValue")
    new_value: str | None = Field(default=None, alias="newValue")
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}
