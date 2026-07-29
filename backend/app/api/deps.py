"""Shared FastAPI dependencies for staff routes.

``StaffActorDep`` is the compatibility hook used by issue #141 (department
assignment). It resolves to the real Bearer-token ``StaffDep`` from issue #72 so
department assignment cannot remain behind a no-op placeholder after merge.
"""

from __future__ import annotations

from app.core.staff_auth import StaffDep, StaffPrincipal, require_staff

# Alias kept for #141 and any other routes that imported StaffActorDep.
StaffActorDep = StaffDep

__all__ = [
    "StaffActorDep",
    "StaffDep",
    "StaffPrincipal",
    "require_staff",
]
