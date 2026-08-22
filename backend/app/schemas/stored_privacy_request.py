"""Persisted privacy-request audit rows (issue #321)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PrivacyRequestAction = Literal[
    "citizen_export",
    "citizen_delete",
    "manual_export",
    "manual_delete",
    "correction",
    "other",
]


class StoredPrivacyRequestAudit(BaseModel):
    request_id: str = Field(alias="requestId")
    action: PrivacyRequestAction
    subject_user_id: str | None = Field(default=None, alias="subjectUserId")
    actor_staff_id: str | None = Field(default=None, alias="actorStaffId")
    actor_username: str | None = Field(default=None, alias="actorUsername")
    summary: str
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}
