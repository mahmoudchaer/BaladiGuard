"""Category similarity for nearby duplicate detection."""

from __future__ import annotations

from typing import Literal

from app.schemas.stored_ticket import PENDING_CLASSIFICATION
from app.services.routing import category_to_department_map

CategoryMatch = Literal["same", "similar"]


def category_match_type(
    query_category: str,
    candidate_category: str,
) -> CategoryMatch | None:
    """Return how two categories relate for duplicate detection, or None if unrelated."""
    if query_category == PENDING_CLASSIFICATION or candidate_category == PENDING_CLASSIFICATION:
        return "same" if query_category == candidate_category else None

    if query_category == candidate_category:
        return "same"

    mapping = category_to_department_map()
    query_department = mapping.get(query_category)
    candidate_department = mapping.get(candidate_category)
    if (
        query_department is not None
        and candidate_department is not None
        and query_department == candidate_department
    ):
        return "similar"
    return None
