"""Staff account store protocol (issue #175)."""

from __future__ import annotations

from typing import Protocol

from app.schemas.staff_user import StoredStaffUser


class StaffUsernameConflictError(Exception):
    """Raised when a username is already claimed."""


class StaffNotFoundError(Exception):
    """Raised when a staffId does not exist."""


class StaffStore(Protocol):
    def create(self, user: StoredStaffUser) -> StoredStaffUser: ...

    def get(self, staff_id: str) -> StoredStaffUser | None: ...

    def get_by_username(self, username: str) -> StoredStaffUser | None: ...

    def list(self) -> list[StoredStaffUser]: ...

    def update(self, user: StoredStaffUser) -> StoredStaffUser: ...

    def clear(self) -> None: ...
