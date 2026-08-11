"""Environment-correct citizen app deep links for notifications (issue #257).

Links use possession-based tracking codes only — never phone, email, access
tokens, internal ticket IDs, or private storage keys.
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.config import Settings, get_settings
from app.utils.ticket_ids import is_valid_tracking_code, normalize_tracking_code

# Local Expo / web default when CITIZEN_APP_BASE_URL is unset in local/dev/test only.
_DEFAULT_LOCAL_CITIZEN_APP_BASE_URL = "http://localhost:8081"
# Staging and production never get a silent localhost default.
_DEPLOYED_ENVS = frozenset({"staging", "production"})

NOTIFICATION_TICKET_PATH_PREFIX = "/t"


def default_citizen_app_base_url_for_env(app_env: str) -> str | None:
    """Return a localhost default only for local/development/test."""
    if app_env in {"local", "development", "test"}:
        return _DEFAULT_LOCAL_CITIZEN_APP_BASE_URL
    return None


def normalize_citizen_app_base_url(raw: str | None) -> str | None:
    """Strip trailing slashes; empty becomes None."""
    if raw is None:
        return None
    cleaned = raw.strip().rstrip("/")
    return cleaned or None


def is_localhost_base_url(base_url: str) -> bool:
    try:
        host = (urlparse(base_url).hostname or "").lower()
    except ValueError:
        return False
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def is_valid_citizen_app_base_url(
    base_url: str,
    *,
    require_https: bool,
) -> bool:
    try:
        parsed = urlparse(base_url)
    except ValueError:
        return False
    if not parsed.scheme or not parsed.netloc:
        return False
    if require_https and parsed.scheme.lower() != "https":
        return False
    if not require_https and parsed.scheme.lower() not in {"http", "https"}:
        return False
    if " " in base_url:
        return False
    return True


def resolve_citizen_app_base_url(settings: Settings | None = None) -> str | None:
    """Resolved base for deep links (configured value or non-prod default)."""
    cfg = settings or get_settings()
    explicit = normalize_citizen_app_base_url(cfg.citizen_app_base_url)
    if explicit:
        return explicit
    return default_citizen_app_base_url_for_env(cfg.app_env)


def build_notification_ticket_path(tracking_code: str) -> str | None:
    """Relative app path `/t/{code}` for Expo deep links."""
    if not tracking_code or not is_valid_tracking_code(tracking_code):
        return None
    code = normalize_tracking_code(tracking_code)
    return f"{NOTIFICATION_TICKET_PATH_PREFIX}/{code}"


def build_ticket_notification_deep_link(
    tracking_code: str | None,
    *,
    settings: Settings | None = None,
) -> str | None:
    """Full HTTPS/HTTP link for SMS/email bodies. None when code/base unavailable."""
    if not tracking_code:
        return None
    path = build_notification_ticket_path(tracking_code)
    if path is None:
        return None
    base = resolve_citizen_app_base_url(settings)
    if not base:
        return None
    require_https = (settings or get_settings()).app_env in _DEPLOYED_ENVS
    if not is_valid_citizen_app_base_url(base, require_https=require_https):
        # Local/dev/test: still allow http. Staging/production force https.
        if not is_valid_citizen_app_base_url(base, require_https=False):
            return None
        if require_https:
            return None
    return f"{base}{path}"
