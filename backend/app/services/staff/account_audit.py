"""Safe account-audit recording (issue #181).

Write failures are logged and never raised so account mutations stay available
for local demos and degraded store backends.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.core.staff_auth import StaffPrincipal
from app.schemas.staff_user import StaffRole
from app.schemas.stored_account_audit import AccountAuditActionType, StoredAccountAudit
from app.services.audit.safe_values import contains_forbidden_audit_key, safe_audit_value

logger = logging.getLogger(__name__)


def generate_account_audit_id() -> str:
    return f"aaud_{uuid4().hex}"


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class AccountAuditService:
    def __init__(self, store=None) -> None:
        self._store = store

    def _resolved_store(self):
        if self._store is not None:
            return self._store
        from app.database.store_factory import get_account_audit_store

        return get_account_audit_store()

    def record_safe(
        self,
        *,
        action_type: AccountAuditActionType,
        target_staff_id: str,
        summary: str,
        actor: StaffPrincipal | None = None,
        actor_id: str | None = None,
        actor_role: StaffRole | None = None,
        previous_value: dict[str, Any] | str | None = None,
        new_value: dict[str, Any] | str | None = None,
        created_at: str | None = None,
    ) -> None:
        """Append an account-audit row; never fails the caller."""
        try:
            resolved_actor_id = actor.staff_id if actor is not None else actor_id
            resolved_actor_role = actor.role if actor is not None else actor_role
            prev = safe_audit_value(previous_value)
            nxt = safe_audit_value(new_value)
            if contains_forbidden_audit_key(
                {
                    "previousValue": prev,
                    "newValue": nxt,
                    "summary": summary,
                }
            ):
                raise ValueError("Account audit payload would expose sensitive fields.")

            entry = StoredAccountAudit(
                auditId=generate_account_audit_id(),
                actionType=action_type,
                actorId=resolved_actor_id,
                actorRole=resolved_actor_role,
                targetStaffId=target_staff_id,
                summary=summary,
                previousValue=prev,
                newValue=nxt,
                createdAt=created_at or _iso_now(),
            )
            self._resolved_store().append(entry)
        except Exception:
            logger.exception(
                "Account audit write failed for target %s action %s; primary mutation kept.",
                target_staff_id,
                action_type,
            )


account_audit_service = AccountAuditService()
