"""Persisted developer-operator control-plane records (issue #320)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

OpsAckStatus = Literal["open", "acknowledged"]
OpsAuditAction = Literal[
    "ALERT_ACKNOWLEDGED",
    "AI_JOB_REPLAYED",
    "REDACTION_JOB_REPLAYED",
    "OPS_SNAPSHOT_READ",
]


class StoredOpsAlertAck(BaseModel):
    alarm_name: str = Field(alias="alarmName")
    status: OpsAckStatus = "acknowledged"
    ack_by: str = Field(alias="ackBy")
    ack_at: str = Field(alias="ackAt")
    note: str | None = None

    model_config = {"populate_by_name": True}


class StoredOpsErrorGroup(BaseModel):
    error_key: str = Field(alias="errorKey")
    category: str
    service: str
    path_group: str | None = Field(default=None, alias="pathGroup")
    status_class: str | None = Field(default=None, alias="statusClass")
    version: str | None = None
    count: int = 1
    first_seen: str = Field(alias="firstSeen")
    last_seen: str = Field(alias="lastSeen")
    last_request_id: str | None = Field(default=None, alias="lastRequestId")
    last_job_id: str | None = Field(default=None, alias="lastJobId")

    model_config = {"populate_by_name": True}


class StoredOpsAudit(BaseModel):
    audit_id: str = Field(alias="auditId")
    action_type: OpsAuditAction = Field(alias="actionType")
    actor_staff_id: str = Field(alias="actorStaffId")
    actor_username: str = Field(alias="actorUsername")
    target: str
    summary: str
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}
