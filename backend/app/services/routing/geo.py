"""Point-in-coverage helpers for municipality geography (issue #322)."""

from __future__ import annotations

from app.schemas.stored_municipality import GeoPolygon, MunicipalityBounds, StoredMunicipality


def point_in_bounds(latitude: float, longitude: float, bounds: MunicipalityBounds) -> bool:
    return (
        bounds.min_latitude <= latitude <= bounds.max_latitude
        and bounds.min_longitude <= longitude <= bounds.max_longitude
    )


def point_in_polygon(latitude: float, longitude: float, polygon: GeoPolygon) -> bool:
    """Ray-casting test. Vertices are [longitude, latitude]."""
    ring = polygon.coordinates
    inside = False
    j = len(ring) - 1
    for i, vertex in enumerate(ring):
        xi, yi = vertex[0], vertex[1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = ((yi > latitude) != (yj > latitude)) and (
            longitude < (xj - xi) * (latitude - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def municipality_covers_point(
    profile: StoredMunicipality, *, latitude: float, longitude: float
) -> bool:
    if not point_in_bounds(latitude, longitude, profile.bounds):
        return False
    if profile.polygon is None:
        return True
    return point_in_polygon(latitude, longitude, profile.polygon)
