"""Privacy-safe helpers for developer-operator projections (issue #320)."""

from __future__ import annotations

import hashlib
import re

from app.core.logging import redact_text

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_PRESIGNED_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_JOB_ID_RE = re.compile(r"^(ai|redaction):[A-Za-z0-9_.:-]+$")
_ALARM_NAME_RE = re.compile(r"^BaladiGuard-[A-Za-z0-9_-]{1,80}$")
_MUNICIPALITY_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

ALLOWED_TIME_RANGES = ("1h", "6h", "24h", "7d")
ALLOWED_SERVICES = {
    "api",
    "ai",
    "redaction",
    "notifications",
    "storage",
    "auth",
    "backup",
    "whatsapp",
    "moderation",
}
ALLOWED_SEVERITIES = {"critical", "warning", "ok", "unknown"}
ALLOWED_JOB_TYPES = {"ai", "redaction", "notifications", "whatsapp", "moderation"}
ALLOWED_ERROR_CATEGORIES = {
    "http_5xx",
    "throttle",
    "auth",
    "dynamodb",
    "s3",
    "ai_provider",
    "redaction",
    "notification",
    "backup",
    "unknown",
}

TIME_RANGE_SECONDS = {"1h": 3600, "6h": 21600, "24h": 86400, "7d": 604800}
TIME_RANGE_PERIOD = {"1h": 60, "6h": 300, "24h": 300, "7d": 3600}


def sanitize_ops_text(value: str | None, *, max_len: int = 160) -> str | None:
    """Bound and redact free text so user content cannot become queries or HTML."""
    if not value:
        return None
    scrubbed = redact_text(value)
    scrubbed = _EMAIL_RE.sub("[REDACTED]", scrubbed)
    scrubbed = _PHONE_RE.sub("[REDACTED]", scrubbed)
    scrubbed = _PRESIGNED_RE.sub("[REDACTED]", scrubbed)
    scrubbed = " ".join(scrubbed.split())
    if not scrubbed:
        return None
    return scrubbed[:max_len]


def hash_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def is_safe_job_id(job_id: str) -> bool:
    return bool(_JOB_ID_RE.match(job_id or ""))


def is_safe_alarm_name(alarm_name: str) -> bool:
    return bool(_ALARM_NAME_RE.match(alarm_name or ""))


def is_safe_municipality_id(value: str | None) -> bool:
    if value is None:
        return True
    return bool(_MUNICIPALITY_RE.match(value))


def parse_time_range(raw: str | None) -> str:
    value = (raw or "1h").strip().lower()
    if value not in ALLOWED_TIME_RANGES:
        raise ValueError("range must be one of 1h, 6h, 24h, 7d.")
    return value


def parse_optional_allowlist(raw: str | None, allowed: set[str], *, field: str) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    value = str(raw).strip().lower()
    if value not in allowed:
        raise ValueError(f"{field} is not an allowed filter value.")
    return value
