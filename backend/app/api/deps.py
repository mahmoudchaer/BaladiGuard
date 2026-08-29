"""Shared FastAPI dependencies for staff and citizen routes.

``StaffActorDep`` is the compatibility hook used by issue #141 (department
assignment). It resolves to the real Bearer-token ``StaffDep`` from issue #72 so
department assignment cannot remain behind a no-op placeholder after merge.

``CitizenDep`` resolves opaque citizen sessions for profile and future
contribution routes (issue #169 / #170).
"""

from __future__ import annotations

from app.core.citizen_auth import (
    CitizenDep,
    CitizenPrincipal,
    ContributionReadyCitizenDep,
    require_citizen,
    require_contribution_ready,
)
from app.core.staff_auth import (
    AdminStaffDep,
    DeveloperOperatorDep,
    MunicipalStaffDep,
    StaffDep,
    StaffPrincipal,
    forbidden,
    require_admin,
    require_developer_operator,
    require_municipal_actor,
    require_staff,
    staff_can_access_ticket,
    staff_can_assign_department,
)

# Alias kept for #141 and any other routes that imported StaffActorDep.
StaffActorDep = MunicipalStaffDep

__all__ = [
    "CitizenDep",
    "CitizenPrincipal",
    "ContributionReadyCitizenDep",
    "DeveloperOperatorDep",
    "MunicipalStaffDep",
    "StaffActorDep",
    "AdminStaffDep",
    "StaffDep",
    "StaffPrincipal",
    "forbidden",
    "require_admin",
    "require_developer_operator",
    "require_municipal_actor",
    "require_citizen",
    "require_contribution_ready",
    "require_staff",
    "staff_can_access_ticket",
    "staff_can_assign_department",
]
