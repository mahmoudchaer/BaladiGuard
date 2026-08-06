"""Account-audit store protocol (issue #181)."""

from __future__ import annotations

from typing import Protocol

from app.schemas.stored_account_audit import StoredAccountAudit


class AccountAuditStore(Protocol):
    def append(self, entry: StoredAccountAudit) -> None: ...

    def list_by_target_staff_id(self, target_staff_id: str) -> list[StoredAccountAudit]: ...

    def list_all(self) -> list[StoredAccountAudit]: ...

    def clear(self) -> None: ...
