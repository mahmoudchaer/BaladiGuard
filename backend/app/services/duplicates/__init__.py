"""Duplicate detection services."""

from app.services.duplicates.detect import (
    OPEN_TICKET_STATUSES,
    effective_ticket_category,
    find_nearby_duplicates,
)
from app.services.duplicates.geo import haversine_meters

__all__ = [
    "OPEN_TICKET_STATUSES",
    "effective_ticket_category",
    "find_nearby_duplicates",
    "haversine_meters",
]
