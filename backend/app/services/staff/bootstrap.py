"""Bootstrap demo staff accounts for local/test environments (issue #175)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.config import Settings, get_settings
from app.core.password_hashing import hash_password
from app.database.staff_store import StaffUsernameConflictError
from app.schemas.staff_user import StoredStaffUser

logger = logging.getLogger(__name__)

BEIRUT_MUNICIPALITY_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ROAD_MAINTENANCE_DEPT = "d1111111-1111-1111-1111-111111111111"
STREET_LIGHTING_DEPT = "d3333333-3333-3333-3333-333333333333"

DEMO_ADMIN_USERNAME = "admin"
DEMO_STAFF_USERNAME = "staff"


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_demo_staff_accounts(*, password: str, now: str | None = None) -> list[StoredStaffUser]:
    stamped = now or _iso_now()
    password_hash = hash_password(password)
    return [
        StoredStaffUser(
            staffId="staff_admin_001",
            username=DEMO_ADMIN_USERNAME,
            name="Demo Administrator",
            email="admin@example.com",
            passwordHash=password_hash,
            role="administrator",
            municipalityId=None,
            departmentIds=None,
            active=True,
            sessionEpoch=0,
            createdAt=stamped,
            updatedAt=stamped,
        ),
        StoredStaffUser(
            staffId="staff_muni_001",
            username=DEMO_STAFF_USERNAME,
            name="Demo Municipal Staff",
            email="staff@example.com",
            passwordHash=password_hash,
            role="municipal_staff",
            municipalityId=BEIRUT_MUNICIPALITY_ID,
            departmentIds=[ROAD_MAINTENANCE_DEPT, STREET_LIGHTING_DEPT],
            active=True,
            sessionEpoch=0,
            createdAt=stamped,
            updatedAt=stamped,
        ),
    ]


def ensure_demo_staff_accounts(
    store=None,
    *,
    settings: Settings | None = None,
) -> int:
    """Idempotently create demo admin + municipal staff accounts.

    Returns the number of accounts created. Existing usernames are left unchanged
    so local password rotations via re-seed/reset remain explicit.
    """
    from app.database.store_factory import get_staff_store

    cfg = settings or get_settings()
    if not cfg.seed_demo_staff:
        return 0

    target = store if store is not None else get_staff_store()
    created = 0
    for account in build_demo_staff_accounts(password=cfg.demo_staff_password):
        existing = target.get_by_username(account.username)
        if existing is not None:
            continue
        try:
            target.create(account)
            created += 1
        except StaffUsernameConflictError:
            continue
    if created:
        logger.info("Bootstrapped %s demo staff account(s).", created)
    return created
