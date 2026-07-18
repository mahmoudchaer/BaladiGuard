"""Category similarity for nearby duplicate detection."""

from __future__ import annotations

from typing import Literal

from app.schemas.stored_ticket import PENDING_CLASSIFICATION

CategoryMatch = Literal["same", "similar"]

# Stable department mapping from docs/complaint-categories.md.
# Categories that share a department are treated as "similar".
CATEGORY_TO_DEPARTMENT: dict[str, str] = {
    "road_damage": "d1111111-1111-1111-1111-111111111111",
    "sidewalk_damage": "d1111111-1111-1111-1111-111111111111",
    "waste": "d2222222-2222-2222-2222-222222222222",
    "street_lighting": "d3333333-3333-3333-3333-333333333333",
    "water_leak": "d4444444-4444-4444-4444-444444444444",
    "noise": "d5555555-5555-5555-5555-555555555555",
    "traffic_signal": "d6666666-6666-6666-6666-666666666666",
    "drainage": "d7777777-7777-7777-7777-777777777777",
    "public_facilities": "d8888888-8888-8888-8888-888888888888",
}


def category_match_type(
    query_category: str,
    candidate_category: str,
) -> CategoryMatch | None:
    """Return how two categories relate for duplicate detection, or None if unrelated."""
    if query_category == PENDING_CLASSIFICATION or candidate_category == PENDING_CLASSIFICATION:
        return "same" if query_category == candidate_category else None

    if query_category == candidate_category:
        return "same"

    query_department = CATEGORY_TO_DEPARTMENT.get(query_category)
    candidate_department = CATEGORY_TO_DEPARTMENT.get(candidate_category)
    if (
        query_department is not None
        and candidate_department is not None
        and query_department == candidate_department
    ):
        return "similar"
    return None
