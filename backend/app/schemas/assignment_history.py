"""Assignment lineage for a single ticket (issue #318)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AssignmentHistoryItem(BaseModel):
    event_id: str = Field(alias="eventId")
    action_type: str = Field(alias="actionType")
    actor_id: str | None = Field(default=None, alias="actorId")
    actor_role: str | None = Field(default=None, alias="actorRole")
    previous_value: str | None = Field(default=None, alias="previousValue")
    new_value: str | None = Field(default=None, alias="newValue")
    summary: str
    occurred_at: str = Field(alias="occurredAt")

    model_config = {"populate_by_name": True}


class AssignmentHistoryResponse(BaseModel):
    ticket_id: str = Field(alias="ticketId")
    items: list[AssignmentHistoryItem] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
