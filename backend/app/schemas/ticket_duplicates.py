"""Bounded duplicate-workspace projections for the staff merge flow (issue #269).

These schemas back the dedicated candidate and comparison endpoints. They stay
deliberately narrow: no citizen contact, tracking codes, raw storage keys, AI
blobs, public drafts, or history. Staff deciding whether two reports are the
same only need the evidence shown here.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.staff_ticket_collection import TicketListLocation
from app.schemas.ticket_response import TicketPriority
from app.schemas.ticket_status import TicketStatus

DUPLICATE_CANDIDATE_DEFAULT_LIMIT = 20
DUPLICATE_CANDIDATE_MAX_LIMIT = 50


class DuplicateCandidateResponse(BaseModel):
    """One mergeable duplicate candidate for the source ticket."""

    ticket_id: str = Field(alias="ticketId")
    ticket_number: str | None = Field(default=None, alias="ticketNumber")
    status: TicketStatus
    category: str
    priority: TicketPriority | None = None
    summary: str
    created_at: str = Field(alias="createdAt")
    location: TicketListLocation
    distance_meters: float | None = Field(default=None, alias="distanceMeters")
    # Presigned GET URL only. The underlying object key stays private.
    image_url: str | None = Field(default=None, alias="imageUrl")
    suggested: bool = False
    score: float | None = None
    category_match: Literal["same", "similar"] | None = Field(default=None, alias="categoryMatch")
    # Returned rows already passed the merge preconditions the API can check.
    mergeable: bool = True

    model_config = {"populate_by_name": True}


class DuplicateCandidatePageResponse(BaseModel):
    items: list[DuplicateCandidateResponse]
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    limit: int = Field(ge=1, le=DUPLICATE_CANDIDATE_MAX_LIMIT)

    model_config = {"populate_by_name": True}


class DuplicateComparisonResponse(BaseModel):
    """Side-by-side comparison projection of a single ticket."""

    ticket_id: str = Field(alias="ticketId")
    ticket_number: str | None = Field(default=None, alias="ticketNumber")
    description: str
    status: TicketStatus
    category: str
    priority: TicketPriority | None = None
    created_at: str = Field(alias="createdAt")
    location: TicketListLocation
    image_url: str | None = Field(default=None, alias="imageUrl")
    distance_meters: float | None = Field(default=None, alias="distanceMeters")

    model_config = {"populate_by_name": True}
