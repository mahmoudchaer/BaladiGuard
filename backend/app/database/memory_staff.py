"""In-memory staff account store with transactional username claims (issue #175)."""

from __future__ import annotations

from threading import Lock

from app.database.staff_store import StaffNotFoundError, StaffUsernameConflictError
from app.schemas.staff_user import StoredStaffUser, staff_username_claim_key


class InMemoryStaffStore:
    def __init__(self) -> None:
        self._users: dict[str, StoredStaffUser] = {}
        self._claims: dict[str, str] = {}
        self._lock = Lock()

    def create(self, user: StoredStaffUser) -> StoredStaffUser:
        claim_key = staff_username_claim_key(user.username)
        with self._lock:
            if claim_key in self._claims:
                raise StaffUsernameConflictError("Username is already claimed.")
            if user.staff_id in self._users:
                raise StaffUsernameConflictError("Staff userId already exists.")
            self._claims[claim_key] = user.staff_id
            self._users[user.staff_id] = user
            return user

    def get(self, staff_id: str) -> StoredStaffUser | None:
        with self._lock:
            return self._users.get(staff_id)

    def get_by_username(self, username: str) -> StoredStaffUser | None:
        claim_key = staff_username_claim_key(username)
        with self._lock:
            staff_id = self._claims.get(claim_key)
            if staff_id is None:
                return None
            return self._users.get(staff_id)

    def update(self, user: StoredStaffUser) -> StoredStaffUser:
        with self._lock:
            existing = self._users.get(user.staff_id)
            if existing is None:
                raise StaffNotFoundError("Staff account not found.")
            if existing.username != user.username:
                raise StaffUsernameConflictError("Username changes are not supported.")
            self._users[user.staff_id] = user
            return user

    def clear(self) -> None:
        with self._lock:
            self._users.clear()
            self._claims.clear()


staff_store = InMemoryStaffStore()
