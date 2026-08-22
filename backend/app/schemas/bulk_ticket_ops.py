"""Bounded, auditable bulk ticket mutations (issue #318)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.ticket_ai_update import AssignTicketDepartmentRequest
from app.schemas.workforce import AssignWorkforceRequest

BULK_TICKET_MAX = 25


class BulkItemResult(BaseModel):
    ticket_id: str = Field(alias="ticketId")
    ok: bool
    code: str | None = None
    message: str | None = None

    model_config = {"populate_by_name": True}


class BulkWorkforceAssignmentRequest(AssignWorkforceRequest):
    ticket_ids: list[str] = Field(alias="ticketIds", min_length=1, max_length=BULK_TICKET_MAX)
    dry_run: bool = Field(default=False, alias="dryRun")

    model_config = {"populate_by_name": True}


class BulkDepartmentAssignmentRequest(AssignTicketDepartmentRequest):
    ticket_ids: list[str] = Field(alias="ticketIds", min_length=1, max_length=BULK_TICKET_MAX)
    dry_run: bool = Field(default=False, alias="dryRun")

    model_config = {"populate_by_name": True}


class BulkMutationResponse(BaseModel):
    dry_run: bool = Field(alias="dryRun")
    attempted: int
    succeeded: int
    failed: int
    items: list[BulkItemResult]

    model_config = {"populate_by_name": True}
