"""Staff authentication for individual MVP staff accounts (issue #175).

Staff sign in via ``POST /v1/staff/login`` against persisted staff-user records.
Passwords are PBKDF2-hashed. Tokens are HMAC-signed and bound to ``staffId`` +
``sessionEpoch`` so logout and deactivation revoke outstanding sessions.
Citizen routes remain separate; staff tokens cannot authenticate them.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.core.password_hashing import verify_password
from app.database.staff_store import StaffNotFoundError
from app.schemas.staff_user import StaffRole, StoredStaffUser
from app.schemas.stored_ticket import StoredTicket
from app.services.routing import load_department_catalog

logger = logging.getLogger(__name__)

DEFAULT_SECRET_KEY = "baladiguard-dev-secret-change-me"
DEFAULT_TOKEN_TTL_SECONDS = 12 * 60 * 60
_TOKEN_VERSION = "v2"

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class StaffPrincipal:
    staff_id: str
    username: str
    name: str
    role: StaffRole
    municipality_id: str | None
    department_ids: list[str] | None
    session_epoch: int


class StaffAuthError(Exception):
    """Invalid credentials or token; never include secrets in the message."""


def _secret_key(settings: Settings) -> str:
    return settings.secret_key or DEFAULT_SECRET_KEY


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def principal_from_user(user: StoredStaffUser) -> StaffPrincipal:
    return StaffPrincipal(
        staff_id=user.staff_id,
        username=user.username,
        name=user.name,
        role=user.role,
        municipality_id=user.municipality_id,
        department_ids=None if user.department_ids is None else list(user.department_ids),
        session_epoch=user.session_epoch,
    )


def issue_staff_access_token(
    principal: StaffPrincipal,
    *,
    settings: Settings | None = None,
    now: int | None = None,
) -> str:
    """Return a compact signed access token bound to staffId + sessionEpoch."""
    cfg = settings or get_settings()
    issued_at = int(time.time() if now is None else now)
    expires_at = issued_at + cfg.staff_token_ttl_seconds
    payload = (
        f"{_TOKEN_VERSION}:{principal.staff_id}:{principal.session_epoch}:{issued_at}:{expires_at}"
    )
    signature = _sign(payload, _secret_key(cfg))
    raw = f"{payload}:{signature}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def verify_staff_access_token(
    token: str,
    *,
    settings: Settings | None = None,
    now: int | None = None,
    staff_store=None,
) -> StaffPrincipal:
    cfg = settings or get_settings()
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        version, staff_id, epoch_raw, issued_raw, expires_raw, signature = raw.rsplit(":", 5)
        issued_at = int(issued_raw)
        expires_at = int(expires_raw)
        session_epoch = int(epoch_raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise StaffAuthError("Invalid staff access token.") from exc

    if version != _TOKEN_VERSION or not staff_id or expires_at < issued_at:
        raise StaffAuthError("Invalid staff access token.")

    expected = _sign(
        f"{version}:{staff_id}:{session_epoch}:{issued_at}:{expires_at}",
        _secret_key(cfg),
    )
    if not hmac.compare_digest(expected, signature):
        raise StaffAuthError("Invalid staff access token.")

    current = int(time.time() if now is None else now)
    if current >= expires_at:
        raise StaffAuthError("Staff access token has expired.")

    from app.database.store_factory import get_staff_store

    store = staff_store if staff_store is not None else get_staff_store()
    user = store.get(staff_id)
    if user is None or not user.active:
        raise StaffAuthError("Staff access token is no longer valid.")
    if int(user.session_epoch) != session_epoch:
        raise StaffAuthError("Staff access token has been revoked.")

    return principal_from_user(user)


def authenticate_staff_credentials(
    username: str,
    password: str,
    *,
    settings: Settings | None = None,
    staff_store=None,
) -> StaffPrincipal:
    """Authenticate against a persisted staff account.

    Invalid credentials and inactive accounts return the same generic error so
    responses do not reveal account existence or active state.
    """
    from app.database.store_factory import get_staff_store

    _ = settings or get_settings()
    store = staff_store if staff_store is not None else get_staff_store()
    user = store.get_by_username(username.strip().lower())
    if user is None or not user.active:
        raise StaffAuthError("Invalid staff username or password.")
    if not verify_password(password, user.password_hash):
        raise StaffAuthError("Invalid staff username or password.")
    return principal_from_user(user)


def deactivate_staff_account(
    staff_id: str,
    *,
    staff_store=None,
    actor: StaffPrincipal | None = None,
) -> StoredStaffUser:
    """Mark inactive and revoke sessions (used by tests / admin tooling)."""
    from app.database.store_factory import get_staff_store
    from app.services.audit.safe_values import staff_snapshot_for_audit
    from app.services.staff.account_audit import account_audit_service

    store = staff_store if staff_store is not None else get_staff_store()
    user = store.get(staff_id)
    if user is None:
        raise StaffNotFoundError("Staff account not found.")
    previous = staff_snapshot_for_audit(
        staff_id=user.staff_id,
        username=user.username,
        name=user.name,
        role=user.role,
        municipality_id=user.municipality_id,
        department_ids=user.department_ids,
        active=user.active,
    )
    stamped = _iso_now()
    updated = user.model_copy(
        update={
            "active": False,
            "session_epoch": user.session_epoch + 1,
            "updated_at": stamped,
        }
    )
    stored = store.update(updated)
    account_audit_service.record_safe(
        action_type="STAFF_DEACTIVATED",
        actor=actor,
        target_staff_id=stored.staff_id,
        summary="Staff account deactivated.",
        previous_value=previous,
        new_value=staff_snapshot_for_audit(
            staff_id=stored.staff_id,
            username=stored.username,
            name=stored.name,
            role=stored.role,
            municipality_id=stored.municipality_id,
            department_ids=stored.department_ids,
            active=stored.active,
        ),
        created_at=stamped,
    )
    return stored


def revoke_staff_sessions(
    staff_id: str,
    *,
    staff_store=None,
    actor: StaffPrincipal | None = None,
) -> StaffPrincipal:
    """Bump sessionEpoch so all outstanding tokens for the account become invalid."""
    from app.database.store_factory import get_staff_store
    from app.services.staff.account_audit import account_audit_service

    store = staff_store if staff_store is not None else get_staff_store()
    user = store.get(staff_id)
    if user is None:
        raise StaffAuthError("Staff account not found.")
    stamped = _iso_now()
    updated = user.model_copy(
        update={
            "session_epoch": user.session_epoch + 1,
            "updated_at": stamped,
        }
    )
    try:
        stored = store.update(updated)
    except StaffNotFoundError as exc:
        raise StaffAuthError("Staff account not found.") from exc
    account_audit_service.record_safe(
        action_type="STAFF_SESSION_REVOKED",
        actor=actor,
        actor_id=actor.staff_id if actor is not None else staff_id,
        actor_role=actor.role if actor is not None else stored.role,
        target_staff_id=stored.staff_id,
        summary="Staff sessions revoked.",
        previous_value=None,
        new_value=None,
        created_at=stamped,
    )
    return principal_from_user(stored)


def unauthorized(
    request: Request,
    message: str = "Staff authentication required.",
) -> HTTPException:
    """401 that never includes ticket contents or internal identifiers."""
    from app.core.errors import get_request_id

    return HTTPException(
        status_code=401,
        detail={
            "error": {
                "code": "UNAUTHORIZED",
                "message": message,
                "details": [],
                "requestId": get_request_id(request),
            }
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden(
    request: Request,
    message: str = "You do not have permission to perform this action.",
) -> HTTPException:
    """403 for authenticated staff principals without route permission."""
    from app.core.errors import get_request_id

    return HTTPException(
        status_code=403,
        detail={
            "error": {
                "code": "FORBIDDEN",
                "message": message,
                "details": [],
                "requestId": get_request_id(request),
            }
        },
    )


def require_staff(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> StaffPrincipal:
    """FastAPI dependency for staff-only routes."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise unauthorized(request)

    try:
        return verify_staff_access_token(credentials.credentials)
    except StaffAuthError:
        raise unauthorized(request) from None


def require_admin(
    request: Request,
    principal: Annotated[StaffPrincipal, Depends(require_staff)],
) -> StaffPrincipal:
    """FastAPI dependency for administrator-only routes."""
    if principal.role != "administrator":
        raise forbidden(request)
    return principal


def require_developer_operator(
    request: Request,
    principal: Annotated[StaffPrincipal, Depends(require_staff)],
) -> StaffPrincipal:
    """FastAPI dependency for developer-operator control-plane routes."""
    if principal.role != "developer_operator":
        raise forbidden(request)
    return principal


def require_municipal_actor(
    request: Request,
    principal: Annotated[StaffPrincipal, Depends(require_staff)],
) -> StaffPrincipal:
    """Staff routes for municipal ticket/workforce work. Operators are excluded."""
    if principal.role == "developer_operator":
        raise forbidden(request)
    return principal


def staff_can_access_ticket(principal: StaffPrincipal, ticket: StoredTicket) -> bool:
    """Return True when a staff principal may read or mutate a ticket resource."""
    if principal.role == "developer_operator":
        return False
    if ticket.municipality_id is not None and ticket.municipality_id != principal.municipality_id:
        return False
    if principal.role == "administrator":
        return True
    if ticket.department_id is None:
        return True
    return ticket.department_id in set(principal.department_ids or [])


def department_municipality_id(department_id: str) -> str | None:
    for department in load_department_catalog():
        if department["departmentId"] == department_id:
            return department.get("municipalityId")
    return None


def staff_can_assign_department(principal: StaffPrincipal, department_id: str) -> bool:
    """Return True when a staff principal may assign a ticket to ``department_id``."""
    if principal.role == "developer_operator":
        return False
    department_municipality = department_municipality_id(department_id)
    if principal.role == "administrator":
        return department_municipality in {None, principal.municipality_id}
    if department_id not in set(principal.department_ids or []):
        return False
    return department_municipality in {None, principal.municipality_id}


StaffDep = Annotated[StaffPrincipal, Depends(require_staff)]
AdminStaffDep = Annotated[StaffPrincipal, Depends(require_admin)]
DeveloperOperatorDep = Annotated[StaffPrincipal, Depends(require_developer_operator)]
MunicipalStaffDep = Annotated[StaffPrincipal, Depends(require_municipal_actor)]

# Re-export for typing convenience
StaffRoleName = Literal["municipal_staff", "administrator", "developer_operator"]
