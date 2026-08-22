"""Privacy-request audit helpers (issue #321)."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from app.database.store_factory import get_privacy_request_audit_store
from app.schemas.stored_privacy_request import PrivacyRequestAction, StoredPrivacyRequestAudit


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def record_privacy_request(
    *,
    action: PrivacyRequestAction,
    summary: str,
    subject_user_id: str | None = None,
    actor_staff_id: str | None = None,
    actor_username: str | None = None,
    created_at: str | None = None,
) -> StoredPrivacyRequestAudit:
    entry = StoredPrivacyRequestAudit(
        requestId=f"prv_{secrets.token_hex(12)}",
        action=action,
        subjectUserId=subject_user_id,
        actorStaffId=actor_staff_id,
        actorUsername=actor_username,
        summary=summary,
        createdAt=created_at or _iso_now(),
    )
    get_privacy_request_audit_store().append(entry)
    return entry
