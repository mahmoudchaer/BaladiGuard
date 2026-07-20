"""Persisted duplicate group created when staff merge reports (issue #27)."""

from pydantic import BaseModel, Field


class StoredDuplicateGroup(BaseModel):
    duplicate_group_id: str = Field(alias="duplicateGroupId")
    canonical_ticket_id: str = Field(alias="canonicalTicketId")
    ticket_ids: list[str] = Field(alias="ticketIds")
    created_at: str = Field(alias="createdAt")
    created_by: str | None = Field(default=None, alias="createdBy")

    model_config = {"populate_by_name": True}
