"""Citizen resolution verification and staff review (issues #248 / #261)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.ticket_status import TicketStatus

ResolutionFeedbackStatus = Literal["CONFIRMED_FIXED", "STILL_UNRESOLVED"]
ResolutionFeedbackReviewStatus = Literal["PENDING", "REVIEWED"]
ResolutionFeedbackReviewAction = Literal["KEEP_RESOLVED", "RETURN_IN_PROGRESS"]

RESOLUTION_FEEDBACK_NOTE_MAX_LENGTH = 500
RESOLUTION_FEEDBACK_STATUSES: tuple[ResolutionFeedbackStatus, ...] = (
    "CONFIRMED_FIXED",
    "STILL_UNRESOLVED",
)


class SubmitResolutionFeedbackRequest(BaseModel):
    status: ResolutionFeedbackStatus
    note: str | None = Field(default=None, max_length=RESOLUTION_FEEDBACK_NOTE_MAX_LENGTH)

    model_config = {"populate_by_name": True}

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if len(trimmed) > RESOLUTION_FEEDBACK_NOTE_MAX_LENGTH:
            raise ValueError(
                f"note must be at most {RESOLUTION_FEEDBACK_NOTE_MAX_LENGTH} characters."
            )
        return trimmed or None


class ReviewResolutionFeedbackRequest(BaseModel):
    action: ResolutionFeedbackReviewAction
    note: str | None = Field(default=None, max_length=RESOLUTION_FEEDBACK_NOTE_MAX_LENGTH)

    model_config = {"populate_by_name": True}

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class CitizenResolutionFeedbackResponse(BaseModel):
    """Owner-only projection. Never includes the private note."""

    tracking_code: str = Field(alias="trackingCode")
    ticket_status: TicketStatus = Field(alias="ticketStatus")
    can_submit: bool = Field(alias="canSubmit")
    status: ResolutionFeedbackStatus | None = None
    submitted_at: str | None = Field(default=None, alias="submittedAt")

    model_config = {"populate_by_name": True}


class StaffResolutionFeedbackResponse(BaseModel):
    """Staff-only projection. Includes the private note and review state."""

    ticket_id: str = Field(alias="ticketId")
    tracking_code: str = Field(alias="trackingCode")
    ticket_status: TicketStatus = Field(alias="ticketStatus")
    status: ResolutionFeedbackStatus | None = None
    note: str | None = None
    submitted_at: str | None = Field(default=None, alias="submittedAt")
    review_status: ResolutionFeedbackReviewStatus | None = Field(default=None, alias="reviewStatus")
    reviewed_at: str | None = Field(default=None, alias="reviewedAt")
    reviewed_by: str | None = Field(default=None, alias="reviewedBy")
    review_action: ResolutionFeedbackReviewAction | None = Field(default=None, alias="reviewAction")
    needs_review: bool = Field(alias="needsReview")

    model_config = {"populate_by_name": True}


class ResolutionReviewQueueItem(BaseModel):
    ticket_id: str = Field(alias="ticketId")
    tracking_code: str = Field(alias="trackingCode")
    municipality_id: str | None = Field(default=None, alias="municipalityId")
    department_id: str | None = Field(default=None, alias="departmentId")
    ticket_status: TicketStatus = Field(alias="ticketStatus")
    feedback_status: ResolutionFeedbackStatus = Field(alias="feedbackStatus")
    submitted_at: str = Field(alias="submittedAt")
    review_status: ResolutionFeedbackReviewStatus = Field(alias="reviewStatus")

    model_config = {"populate_by_name": True}


class ResolutionReviewQueueResponse(BaseModel):
    items: list[ResolutionReviewQueueItem]

    model_config = {"populate_by_name": True}


class StoredResolutionReview(BaseModel):
    review_id: str = Field(alias="reviewId")
    ticket_id: str = Field(alias="ticketId")
    tracking_code: str = Field(alias="trackingCode")
    municipality_id: str | None = Field(default=None, alias="municipalityId")
    department_id: str | None = Field(default=None, alias="departmentId")
    ticket_status: TicketStatus = Field(alias="ticketStatus")
    feedback_status: ResolutionFeedbackStatus = Field(alias="feedbackStatus")
    submitted_at: str = Field(alias="submittedAt")
    review_status: ResolutionFeedbackReviewStatus = Field(alias="reviewStatus")

    model_config = {"populate_by_name": True}
