"""Curated Lebanon place index used when Amazon Location is not configured."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class LocalPlace:
    label: str
    address_text: str
    latitude: float
    longitude: float
    aliases: tuple[str, ...] = ()


LOCAL_PLACES: tuple[LocalPlace, ...] = (
    LocalPlace(
        label="AUB Main Gate",
        address_text="Near AUB Main Gate, Hamra, Beirut",
        latitude=33.896112,
        longitude=35.478419,
        aliases=("aub", "hamra", "bliss"),
    ),
    LocalPlace(
        label="Downtown Beirut",
        address_text="Downtown Beirut, Lebanon",
        latitude=33.895918,
        longitude=35.506111,
        aliases=("downtown", "centre ville", "nejmeh"),
    ),
    LocalPlace(
        label="Verdun Street",
        address_text="Verdun Street, Beirut",
        latitude=33.88694,
        longitude=35.48306,
        aliases=("verdun",),
    ),
    LocalPlace(
        label="Sassine Square",
        address_text="Sassine Square, Achrafieh, Beirut",
        latitude=33.8865,
        longitude=35.5194,
        aliases=("sassine", "achrafieh"),
    ),
    LocalPlace(
        label="Mar Mikhael",
        address_text="Mar Mikhael, Beirut",
        latitude=33.8992,
        longitude=35.5287,
        aliases=("mar mikhael", "marmikhael"),
    ),
    LocalPlace(
        label="Al Tall Square",
        address_text="Al Tall Square, Tripoli",
        latitude=34.4361,
        longitude=35.8372,
        aliases=("tripoli", "al tall", "el mina", "mina"),
    ),
)

# Seeded municipality bounding boxes used for local coordinate checks.
# Routing still uses per-municipality profiles; this union only gates intake.
BEIRUT_BOUNDS = {
    "min_latitude": 33.84,
    "max_latitude": 33.93,
    "min_longitude": 35.45,
    "max_longitude": 35.58,
}

TRIPOLI_BOUNDS = {
    "min_latitude": 34.40,
    "max_latitude": 34.48,
    "min_longitude": 35.80,
    "max_longitude": 35.88,
}

SERVICE_AREA_BOUNDS: tuple[dict[str, float], ...] = (BEIRUT_BOUNDS, TRIPOLI_BOUNDS)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def search_local_places_by_text(query: str) -> LocalPlace | None:
    normalized = _normalize(query)
    if not normalized:
        return None

    best: LocalPlace | None = None
    best_score = 0
    for place in LOCAL_PLACES:
        candidates = (place.label, place.address_text, *place.aliases)
        score = 0
        for candidate in candidates:
            candidate_norm = _normalize(candidate)
            if normalized == candidate_norm:
                score = max(score, 100)
            elif normalized in candidate_norm or candidate_norm in normalized:
                score = max(score, 80)
            else:
                overlap = sum(1 for token in normalized.split() if token in candidate_norm)
                score = max(score, overlap * 20)
        if score > best_score:
            best = place
            best_score = score

    return best if best_score >= 40 else None


def search_local_places_by_position(
    latitude: float,
    longitude: float,
    *,
    max_distance_meters: float = 2_500,
) -> LocalPlace | None:
    nearest: LocalPlace | None = None
    nearest_distance = float("inf")
    for place in LOCAL_PLACES:
        distance = haversine_meters(latitude, longitude, place.latitude, place.longitude)
        if distance < nearest_distance:
            nearest = place
            nearest_distance = distance
    if nearest is None or nearest_distance > max_distance_meters:
        return None
    return nearest


def _in_bounds(latitude: float, longitude: float, bounds: dict[str, float]) -> bool:
    return (
        bounds["min_latitude"] <= latitude <= bounds["max_latitude"]
        and bounds["min_longitude"] <= longitude <= bounds["max_longitude"]
    )


def is_within_beirut_bounds(latitude: float, longitude: float) -> bool:
    return _in_bounds(latitude, longitude, BEIRUT_BOUNDS)


def is_within_service_area(latitude: float, longitude: float) -> bool:
    """Accept coordinates covered by any active municipality, not only Beirut."""
    if any(_in_bounds(latitude, longitude, box) for box in SERVICE_AREA_BOUNDS):
        return True
    try:
        from app.database.store_factory import get_municipality_store
        from app.services.routing.geo import municipality_covers_point

        for profile in get_municipality_store().list_all():
            if profile.active and municipality_covers_point(
                profile, latitude=latitude, longitude=longitude
            ):
                return True
    except Exception:  # pragma: no cover - store unavailable during early boot
        return False
    return False
