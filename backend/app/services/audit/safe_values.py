"""Safe audit payload helpers (issue #181).

Audit previous/new value fields may only carry non-secret, non-citizen fields.
"""

from __future__ import annotations

import json
from typing import Any

# Keys that must never appear in audit previous/new value payloads.
FORBIDDEN_AUDIT_KEYS = frozenset(
    {
        "password",
        "passwordhash",
        "password_hash",
        "token",
        "accesstoken",
        "access_token",
        "refreshtoken",
        "refresh_token",
        "code",
        "resetcode",
        "reset_code",
        "codehash",
        "code_hash",
        "otp",
        "otpcode",
        "otp_code",
        "secret",
        "secretkey",
        "secret_key",
        "authorization",
        "sessiontoken",
        "session_token",
    }
)

# Staff fields allowed in account-audit previous/new values.
SAFE_STAFF_AUDIT_FIELDS = frozenset(
    {
        "staffId",
        "username",
        "name",
        "role",
        "municipalityId",
        "departmentIds",
        "active",
    }
)


def _normalize_key(key: str) -> str:
    return key.replace("-", "").replace("_", "").lower()


def contains_forbidden_audit_key(payload: Any) -> bool:
    """True when any nested mapping uses a forbidden secret-like key."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if _normalize_key(str(key)) in FORBIDDEN_AUDIT_KEYS:
                return True
            if contains_forbidden_audit_key(value):
                return True
        return False
    if isinstance(payload, list):
        return any(contains_forbidden_audit_key(item) for item in payload)
    return False


# Broader than key-name checks: bare "code" is too common in free text / IDs.
_STRING_SENSITIVE_MARKERS = frozenset(marker for marker in FORBIDDEN_AUDIT_KEYS if marker != "code")


def _string_contains_sensitive_material(value: str) -> bool:
    """Detect secret-like key material embedded in free-form audit strings."""
    normalized = _normalize_key(value)
    return any(marker in normalized for marker in _STRING_SENSITIVE_MARKERS)


def sanitize_audit_mapping(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return only safe staff fields; drop everything else."""
    if not payload:
        return None
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in SAFE_STAFF_AUDIT_FIELDS:
            continue
        if _normalize_key(key) in FORBIDDEN_AUDIT_KEYS:
            continue
        cleaned[key] = value
    return cleaned or None


def safe_audit_value(payload: dict[str, Any] | str | None) -> str | None:
    """Serialize a safe previous/new value for persistence."""
    if payload is None:
        return None
    if isinstance(payload, str):
        stripped = payload.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return safe_audit_value(parsed)
        if _string_contains_sensitive_material(stripped):
            raise ValueError("Audit string payload contains forbidden sensitive material.")
        return stripped
    cleaned = sanitize_audit_mapping(payload)
    if cleaned is None:
        return None
    if contains_forbidden_audit_key(cleaned):
        raise ValueError("Audit payload contains forbidden sensitive keys.")
    return json.dumps(cleaned, sort_keys=True, separators=(",", ":"))


def staff_snapshot_for_audit(
    *,
    staff_id: str,
    username: str | None = None,
    name: str | None = None,
    role: str | None = None,
    municipality_id: str | None = None,
    department_ids: list[str] | None = None,
    active: bool | None = None,
) -> dict[str, Any]:
    """Build a safe staff snapshot for account-audit previous/new values."""
    snapshot: dict[str, Any] = {"staffId": staff_id}
    if username is not None:
        snapshot["username"] = username
    if name is not None:
        snapshot["name"] = name
    if role is not None:
        snapshot["role"] = role
    if municipality_id is not None or role == "administrator":
        snapshot["municipalityId"] = municipality_id
    if department_ids is not None or role == "administrator":
        snapshot["departmentIds"] = department_ids
    if active is not None:
        snapshot["active"] = active
    return snapshot
