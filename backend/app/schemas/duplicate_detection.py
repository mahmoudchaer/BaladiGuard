"""Schemas for nearby duplicate detection (issue #25)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.ticket_status import TicketStatus

CategoryMatch = Literal["same", "similar"]


class NearbyDuplicateMatch(BaseModel):
    ticket_id: str = Field(alias="ticketId")
    distance_meters: float = Field(alias="distanceMeters")
    score: float
    category: str
    category_match: CategoryMatch = Field(alias="categoryMatch")
    status: TicketStatus

    model_config = {"populate_by_name": True}


class NearbyDuplicateDetectionResult(BaseModel):
    matches: list[NearbyDuplicateMatch]
    distance_threshold_meters: float = Field(alias="distanceThresholdMeters")
    query_category: str = Field(alias="queryCategory")
    query_latitude: float = Field(alias="queryLatitude")
    query_longitude: float = Field(alias="queryLongitude")

    model_config = {"populate_by_name": True}
