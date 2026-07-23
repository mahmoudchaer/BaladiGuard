"""Nearby duplicate detection for open tickets (issue #25)."""

from __future__ import annotations

from collections.abc import Sequence

from app.config import get_settings
from app.schemas.duplicate_detection import (
    NearbyDuplicateDetectionResult,
    NearbyDuplicateMatch,
)
from app.schemas.stored_ticket import PENDING_CLASSIFICATION, StoredTicket
from app.schemas.ticket_status import TicketStatus
from app.services.duplicates.category_similarity import category_match_type
from app.services.duplicates.geo import haversine_meters

OPEN_TICKET_STATUSES: frozenset[TicketStatus] = frozenset(
    {
        "SUBMITTED",
        "UNDER_REVIEW",
        "ASSIGNED",
        "IN_PROGRESS",
    }
)

DISTANCE_SCORE_WEIGHT = 0.65
CATEGORY_SCORE_WEIGHT = 0.35


def effective_ticket_category(ticket: StoredTicket) -> str:
    """Prefer the staff-approved category when present."""
    if ticket.final_category:
        return ticket.final_category
    if ticket.ai_suggested_category:
        return ticket.ai_suggested_category
    if ticket.category == PENDING_CLASSIFICATION:
        return PENDING_CLASSIFICATION
    return ticket.category


def duplicate_score(
    *,
    distance_meters: float,
    distance_threshold_meters: float,
    category_match: str,
    same_category_weight: float,
    similar_category_weight: float,
) -> float:
    """Combine distance closeness and category similarity into a 0..1 score."""
    if distance_threshold_meters <= 0:
        distance_component = 0.0
    else:
        distance_component = max(0.0, 1.0 - (distance_meters / distance_threshold_meters))

    category_weight = same_category_weight if category_match == "same" else similar_category_weight
    score = (DISTANCE_SCORE_WEIGHT * distance_component) + (CATEGORY_SCORE_WEIGHT * category_weight)
    return round(min(1.0, max(0.0, score)), 4)


def find_nearby_duplicates(
    *,
    category: str,
    latitude: float,
    longitude: float,
    tickets: Sequence[StoredTicket],
    distance_threshold_meters: float | None = None,
    min_score: float | None = None,
    exclude_ticket_id: str | None = None,
) -> NearbyDuplicateDetectionResult:
    """Find open tickets near the query point in the same or similar category.

    This is a pure detection helper for issue #25. It does not persist duplicate
    groups or mutate tickets; staff merge / grouping belongs to later issues.
    """
    settings = get_settings()
    threshold = (
        settings.duplicate_distance_threshold_m
        if distance_threshold_meters is None
        else distance_threshold_meters
    )
    score_floor = settings.duplicate_min_score if min_score is None else min_score
    same_weight = settings.duplicate_same_category_weight
    similar_weight = settings.duplicate_similar_category_weight

    matches: list[NearbyDuplicateMatch] = []
    for ticket in tickets:
        if exclude_ticket_id is not None and ticket.ticket_id == exclude_ticket_id:
            continue
        if ticket.status not in OPEN_TICKET_STATUSES:
            continue

        candidate_category = effective_ticket_category(ticket)
        match_type = category_match_type(category, candidate_category)
        if match_type is None:
            continue

        distance = haversine_meters(
            latitude,
            longitude,
            ticket.location.latitude,
            ticket.location.longitude,
        )
        if distance > threshold:
            continue

        score = duplicate_score(
            distance_meters=distance,
            distance_threshold_meters=threshold,
            category_match=match_type,
            same_category_weight=same_weight,
            similar_category_weight=similar_weight,
        )
        if score < score_floor:
            continue

        matches.append(
            NearbyDuplicateMatch(
                ticketId=ticket.ticket_id,
                distanceMeters=round(distance, 2),
                score=score,
                category=candidate_category,
                categoryMatch=match_type,
                status=ticket.status,
            )
        )

    matches.sort(key=lambda item: (-item.score, item.distance_meters, item.ticket_id))
    return NearbyDuplicateDetectionResult(
        matches=matches,
        distanceThresholdMeters=threshold,
        queryCategory=category,
        queryLatitude=latitude,
        queryLongitude=longitude,
    )
