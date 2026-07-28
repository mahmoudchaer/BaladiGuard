"""Staff authentication helpers for issue #72.

MVP contract (extends the #71 frontend session):
- Staff sign in via ``POST /v1/staff/login`` with username/password.
- Backend issues a signed Bearer access token (HMAC-SHA256, no extra deps).
- Staff-only ticket routes require ``Authorization: Bearer <token>``.
- Citizen submit + tracking lookup stay public.

This is a temporary shared-credential MVP, not Cognito. Rotate
``SECRET_KEY`` / staff password before any real deployment.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

# Default matches admin Vite demo credentials so local/CI stay aligned.
DEFAULT_STAFF_USERNAME = "staff"
DEFAULT_STAFF_PASSWORD = "staff-demo-password"
DEFAULT_SECRET_KEY = "baladiguard-dev-secret-change-me"
DEFAULT_TOKEN_TTL_SECONDS = 12 * 60 * 60

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class StaffPrincipal:
    username: str


class StaffAuthError(Exception):
    """Invalid credentials or token; never include secrets in the message."""


def _secret_key(settings: Settings) -> str:
    return settings.secret_key or DEFAULT_SECRET_KEY


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_staff_access_token(
    username: str,
    *,
    settings: Settings | None = None,
    now: int | None = None,
) -> str:
    """Return a compact signed access token for the given staff username."""
    cfg = settings or get_settings()
    issued_at = int(time.time() if now is None else now)
    expires_at = issued_at + cfg.staff_token_ttl_seconds
    payload = f"{username}:{issued_at}:{expires_at}"
    signature = _sign(payload, _secret_key(cfg))
    raw = f"{payload}:{signature}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def verify_staff_access_token(
    token: str,
    *,
    settings: Settings | None = None,
    now: int | None = None,
) -> StaffPrincipal:
    cfg = settings or get_settings()
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        username, issued_raw, expires_raw, signature = raw.rsplit(":", 3)
        issued_at = int(issued_raw)
        expires_at = int(expires_raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise StaffAuthError("Invalid staff access token.") from exc

    if not username or expires_at < issued_at:
        raise StaffAuthError("Invalid staff access token.")

    expected = _sign(f"{username}:{issued_at}:{expires_at}", _secret_key(cfg))
    if not hmac.compare_digest(expected, signature):
        raise StaffAuthError("Invalid staff access token.")

    current = int(time.time() if now is None else now)
    if current >= expires_at:
        raise StaffAuthError("Staff access token has expired.")

    return StaffPrincipal(username=username)


def authenticate_staff_credentials(
    username: str,
    password: str,
    *,
    settings: Settings | None = None,
) -> StaffPrincipal:
    cfg = settings or get_settings()
    expected_username = cfg.staff_username
    expected_password = cfg.staff_password
    user_ok = hmac.compare_digest(username.strip(), expected_username)
    pass_ok = hmac.compare_digest(password, expected_password)
    if not (user_ok and pass_ok):
        raise StaffAuthError("Invalid staff username or password.")
    return StaffPrincipal(username=expected_username)


def unauthorized(request: Request, message: str = "Staff authentication required.") -> HTTPException:
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


def require_staff(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> StaffPrincipal:
    """FastAPI dependency for staff-only routes (issue #72)."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise unauthorized(request)

    try:
        return verify_staff_access_token(credentials.credentials)
    except StaffAuthError:
        # Same generic message for missing/invalid/expired — do not leak why.
        raise unauthorized(request) from None
