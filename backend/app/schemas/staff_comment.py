"""Private, append-only staff ticket comments (issue #246)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class CreateStaffCommentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    mentioned_staff_ids: list[str] = Field(
        default_factory=list, alias="mentionedStaffIds", max_length=20
    )

    model_config = {"populate_by_name": True}

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text is required.")
        return value


class StoredStaffComment(BaseModel):
    comment_id: str = Field(alias="commentId")
    ticket_id: str = Field(alias="ticketId")
    author_staff_id: str = Field(alias="authorStaffId")
    text: str
    mentioned_staff_ids: list[str] = Field(alias="mentionedStaffIds")
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class StaffCommentResponse(BaseModel):
    comment_id: str = Field(alias="commentId")
    ticket_id: str = Field(alias="ticketId")
    author_staff_id: str = Field(alias="authorStaffId")
    author_display_name: str = Field(alias="authorDisplayName")
    text: str
    mentioned_staff_ids: list[str] = Field(alias="mentionedStaffIds")
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class ActivityEvent(BaseModel):
    event_id: str = Field(alias="eventId")
    event_type: str = Field(alias="eventType")
    occurred_at: str = Field(alias="occurredAt")
    actor_display_name: str | None = Field(default=None, alias="actorDisplayName")
    details: dict[str, str] = Field(default_factory=dict)
    source_reference: str = Field(alias="sourceReference")

    model_config = {"populate_by_name": True}


class ActivityTimelineResponse(BaseModel):
    events: list[ActivityEvent]
    next_cursor: str | None = Field(default=None, alias="nextCursor")

    model_config = {"populate_by_name": True}
