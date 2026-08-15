"""Maintenance completion evidence records (issue #248)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

WorkOrderEvidenceKind = Literal["BEFORE", "AFTER", "ORIGINAL_REPORT"]
WorkOrderEvidenceSource = Literal["UPLOAD", "TICKET_ORIGINAL"]

EVIDENCE_KINDS: tuple[WorkOrderEvidenceKind, ...] = ("BEFORE", "AFTER", "ORIGINAL_REPORT")
UPLOADABLE_EVIDENCE_KINDS: frozenset[WorkOrderEvidenceKind] = frozenset({"BEFORE", "AFTER"})


class StoredWorkOrderEvidence(BaseModel):
    evidence_id: str = Field(alias="evidenceId")
    ticket_id: str = Field(alias="ticketId")
    work_order_id: str = Field(alias="workOrderId")
    kind: WorkOrderEvidenceKind
    object_key: str = Field(alias="objectKey")
    content_type: str = Field(alias="contentType")
    uploaded_by: str = Field(alias="uploadedBy")
    created_at: str = Field(alias="createdAt")
    source: WorkOrderEvidenceSource = "UPLOAD"

    model_config = {"populate_by_name": True}


class WorkOrderEvidenceResponse(BaseModel):
    evidence_id: str = Field(alias="evidenceId")
    ticket_id: str = Field(alias="ticketId")
    work_order_id: str = Field(alias="workOrderId")
    kind: WorkOrderEvidenceKind
    object_key: str = Field(alias="objectKey")
    content_type: str = Field(alias="contentType")
    uploaded_by: str = Field(alias="uploadedBy")
    created_at: str = Field(alias="createdAt")
    source: WorkOrderEvidenceSource
    photo_url: str | None = Field(default=None, alias="photoUrl")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_stored(
        cls,
        evidence: StoredWorkOrderEvidence,
        *,
        photo_url: str | None = None,
    ) -> WorkOrderEvidenceResponse:
        payload = evidence.model_dump(by_alias=True)
        payload["photoUrl"] = photo_url
        return cls.model_validate(payload)
