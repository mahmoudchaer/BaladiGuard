"""Curated Beirut place index used when Amazon Location is not configured."""

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
)

# Rough Beirut metro bounding box used for local coordinate checks.
BEIRUT_BOUNDS = {
    "min_latitude": 33.84,
    "max_latitude": 33.93,
    "min_longitude": 35.45,
    "max_longitude": 35.58,
}


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


def is_within_beirut_bounds(latitude: float, longitude: float) -> bool:
    return (
        BEIRUT_BOUNDS["min_latitude"] <= latitude <= BEIRUT_BOUNDS["max_latitude"]
        and BEIRUT_BOUNDS["min_longitude"] <= longitude <= BEIRUT_BOUNDS["max_longitude"]
    )
