"""Shared FastAPI dependencies for staff and citizen routes.

``StaffActorDep`` is the compatibility hook used by issue #141 (department
assignment). It resolves to the real Bearer-token ``StaffDep`` from issue #72 so
department assignment cannot remain behind a no-op placeholder after merge.

``CitizenDep`` resolves opaque citizen sessions for profile and future
contribution routes (issue #169 / #170).
"""

from __future__ import annotations

from app.core.citizen_auth import CitizenDep, CitizenPrincipal, require_citizen
from app.core.staff_auth import StaffDep, StaffPrincipal, require_staff

# Alias kept for #141 and any other routes that imported StaffActorDep.
StaffActorDep = StaffDep

__all__ = [
    "CitizenDep",
    "CitizenPrincipal",
    "StaffActorDep",
    "StaffDep",
    "StaffPrincipal",
    "require_citizen",
    "require_staff",
]
