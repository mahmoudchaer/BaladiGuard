"""Bootstrap demo staff accounts for local/test environments (issue #175)."""

from __future__ import annotations

import logging
import os
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
DEMO_OPERATOR_USERNAME = "operator"


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
        StoredStaffUser(
            staffId="staff_ops_001",
            username=DEMO_OPERATOR_USERNAME,
            name="Demo Developer Operator",
            email="operator@example.com",
            passwordHash=password_hash,
            role="developer_operator",
            municipalityId=None,
            departmentIds=None,
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
    """Idempotently create demo admin + municipal staff + developer-operator accounts.

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


def ensure_developer_operator_bootstrap(
    store=None,
    *,
    settings: Settings | None = None,
) -> int:
    """Create the first developer-operator from env when the username is unset."""
    from app.database.store_factory import build_staff_store

    _settings = settings or get_settings()
    username = (os.getenv("DEVELOPER_OPERATOR_USERNAME", "") or "").strip().lower()
    password = (os.getenv("DEVELOPER_OPERATOR_PASSWORD", "") or "").strip()
    email = (os.getenv("DEVELOPER_OPERATOR_EMAIL", "") or "ops@example.com").strip()
    if not username or not password or len(password) < 8:
        return 0
    target = store if store is not None else build_staff_store(_settings)
    if target.get_by_username(username) is not None:
        return 0
    stamped = _iso_now()
    account = StoredStaffUser(
        staffId="staff_ops_bootstrap",
        username=username,
        name="Developer Operator",
        email=email,
        passwordHash=hash_password(password),
        role="developer_operator",
        municipalityId=None,
        departmentIds=None,
        active=True,
        sessionEpoch=0,
        createdAt=stamped,
        updatedAt=stamped,
    )
    try:
        target.create(account)
    except StaffUsernameConflictError:
        return 0
    logger.info("Bootstrapped developer-operator username=%s.", username)
    return 1
