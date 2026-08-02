"""Citizen session authentication helpers (issue #169 foundation for #170).

Citizen Bearer tokens are opaque server-side sessions. Only a keyed hash is stored.
Staff tokens cannot authenticate citizen routes (wrong audience → 401).

Account-wide revocation uses a strongly consistent ``sessionEpoch`` on the citizen
record (checked on every authentication). Per-session ``revokedAt`` remains a
best-effort cleanup/audit marker and is not the sole revocation authority.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Protocol

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.core.staff_auth import DEFAULT_SECRET_KEY
from app.database.memory_citizen_session import citizen_session_store
from app.schemas.citizen_session import StoredCitizenSession

CITIZEN_SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class CitizenPrincipal:
    user_id: str
    session_id: str


class CitizenSessionStore(Protocol):
    def create(self, session: StoredCitizenSession) -> StoredCitizenSession: ...

    def get(self, session_id: str) -> StoredCitizenSession | None: ...

    def revoke(
        self,
        session_id: str,
        *,
        revoked_at: str,
        reason: str,
    ) -> StoredCitizenSession | None: ...

    def revoke_all_for_user(
        self,
        user_id: str,
        *,
        revoked_at: str,
        reason: str,
    ) -> int: ...


class CitizenUserLookup(Protocol):
    def get(self, user_id: str): ...


def _secret_key(settings: Settings) -> str:
    return settings.secret_key or DEFAULT_SECRET_KEY


def hash_citizen_token(token: str, *, settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    return hmac.new(
        _secret_key(cfg).encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def issue_citizen_session(
    user_id: str,
    *,
    session_epoch: int = 0,
    session_store: CitizenSessionStore | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> tuple[str, StoredCitizenSession]:
    """Create a 30-day absolute citizen session and return (raw_token, record)."""
    store = session_store or citizen_session_store
    cfg = settings or get_settings()
    moment = now or _utcnow()
    session_id = f"csess_{secrets.token_hex(16)}"
    secret = secrets.token_urlsafe(32)
    raw_token = f"{session_id}.{secret}"
    expires = moment + timedelta(seconds=CITIZEN_SESSION_TTL_SECONDS)
    record = StoredCitizenSession(
        sessionId=session_id,
        tokenHash=hash_citizen_token(raw_token, settings=cfg),
        userId=user_id,
        sessionEpoch=session_epoch,
        createdAt=_iso(moment),
        expiresAt=_iso(expires),
        ttl=int(expires.timestamp()),
    )
    store.create(record)
    return raw_token, record


def verify_citizen_access_token(
    token: str,
    *,
    session_store: CitizenSessionStore | None = None,
    citizen_store: CitizenUserLookup | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> CitizenPrincipal:
    store = session_store or citizen_session_store
    cfg = settings or get_settings()
    moment = now or _utcnow()

    if "." not in token:
        raise CitizenAuthError("Invalid citizen access token.")
    session_id, _separator, _secret = token.partition(".")
    if not session_id.startswith("csess_") or not _secret:
        raise CitizenAuthError("Invalid citizen access token.")

    session = store.get(session_id)
    if session is None:
        raise CitizenAuthError("Invalid citizen access token.")

    expected = session.token_hash
    actual = hash_citizen_token(token, settings=cfg)
    if not hmac.compare_digest(expected, actual):
        raise CitizenAuthError("Invalid citizen access token.")

    if session.revoked_at is not None:
        raise CitizenAuthError("Citizen session has been revoked.")

    try:
        expires_at = datetime.fromisoformat(session.expires_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CitizenAuthError("Invalid citizen access token.") from exc

    if moment >= expires_at:
        raise CitizenAuthError("Citizen session has expired.")

    users = citizen_store
    if users is None:
        from app.database.store_factory import get_citizen_store

        users = get_citizen_store()
    # DynamoCitizenStore.get uses ConsistentRead so sessionEpoch is not stale
    # immediately after a phone-change / revocation write.
    user = users.get(session.user_id)
    if user is None or not getattr(user, "active", False):
        raise CitizenAuthError("Citizen session is no longer valid.")
    if int(getattr(user, "session_epoch", 0)) != int(session.session_epoch):
        raise CitizenAuthError("Citizen session has been revoked.")

    return CitizenPrincipal(user_id=session.user_id, session_id=session.session_id)


class CitizenAuthError(Exception):
    """Invalid/expired/revoked/wrong-audience citizen credentials."""


def unauthorized(
    request: Request,
    message: str = "Citizen authentication required.",
) -> HTTPException:
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


def contribution_profile_required(
    request: Request,
    message: str = "Complete your profile before submitting a report.",
) -> HTTPException:
    from app.core.errors import get_request_id

    return HTTPException(
        status_code=403,
        detail={
            "error": {
                "code": "CONTRIBUTION_PROFILE_REQUIRED",
                "message": message,
                "details": [],
                "requestId": get_request_id(request),
            }
        },
    )


def require_citizen(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> CitizenPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise unauthorized(request)

    try:
        from app.database.store_factory import get_citizen_session_store, get_citizen_store

        return verify_citizen_access_token(
            credentials.credentials,
            session_store=get_citizen_session_store(),
            citizen_store=get_citizen_store(),
        )
    except CitizenAuthError:
        raise unauthorized(request) from None


def require_contribution_ready(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> CitizenPrincipal:
    """Require an active citizen session that is contribution-ready (issue #173).

    Missing/invalid/revoked/inactive sessions → ``401 UNAUTHORIZED``.
    Active but incomplete profiles → ``403 CONTRIBUTION_PROFILE_REQUIRED``.
    """
    principal = require_citizen(request, credentials)
    from app.database.store_factory import get_citizen_store
    from app.services.citizens.service import is_contribution_ready

    user = get_citizen_store().get(principal.user_id)
    if user is None or not getattr(user, "active", False):
        raise unauthorized(request)
    if not is_contribution_ready(user):
        raise contribution_profile_required(request)
    return principal


def optional_citizen(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> CitizenPrincipal | None:
    """Return the citizen principal when a Bearer token is present; else None.

    Malformed/expired/wrong-audience credentials still raise ``401`` so clients
    cannot silently fall back to guest behavior with a bad token.
    """
    if credentials is None or not credentials.credentials:
        return None
    if credentials.scheme.lower() != "bearer":
        raise unauthorized(request)
    return require_citizen(request, credentials)


CitizenDep = Annotated[CitizenPrincipal, Depends(require_citizen)]
ContributionReadyCitizenDep = Annotated[CitizenPrincipal, Depends(require_contribution_ready)]
OptionalCitizenDep = Annotated[CitizenPrincipal | None, Depends(optional_citizen)]
