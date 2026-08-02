"""In-memory citizen account store with transactional phone claims (issue #169)."""

from __future__ import annotations

from threading import Lock

from app.database.citizen_store import (
    CitizenNotFoundError,
    CitizenPhoneMismatchError,
    PhoneClaimConflictError,
)
from app.schemas.citizen import StoredCitizenUser
from app.utils.phone import phone_claim_key


class InMemoryCitizenStore:
    def __init__(self) -> None:
        self._users: dict[str, StoredCitizenUser] = {}
        self._claims: dict[str, str] = {}  # phoneKey -> userId
        self._lock = Lock()

    def create(self, user: StoredCitizenUser) -> StoredCitizenUser:
        claim_key = phone_claim_key(user.phone)
        with self._lock:
            if claim_key in self._claims:
                raise PhoneClaimConflictError("Phone number is already claimed.")
            if user.user_id in self._users:
                raise PhoneClaimConflictError("Citizen userId already exists.")
            self._claims[claim_key] = user.user_id
            self._users[user.user_id] = user
            return user

    def get(self, user_id: str) -> StoredCitizenUser | None:
        with self._lock:
            return self._users.get(user_id)

    def get_by_phone(self, canonical_phone: str) -> StoredCitizenUser | None:
        claim_key = phone_claim_key(canonical_phone)
        with self._lock:
            user_id = self._claims.get(claim_key)
            if user_id is None:
                return None
            return self._users.get(user_id)

    def update(self, user: StoredCitizenUser) -> StoredCitizenUser:
        with self._lock:
            existing = self._users.get(user.user_id)
            if existing is None:
                raise CitizenNotFoundError("Citizen not found.")
            if existing.phone != user.phone:
                raise CitizenPhoneMismatchError(
                    "Phone changes must use change_phone(), not update()."
                )
            self._users[user.user_id] = user
            return user

    def change_phone(
        self,
        *,
        user_id: str,
        old_phone: str,
        updated_user: StoredCitizenUser,
    ) -> StoredCitizenUser:
        if updated_user.user_id != user_id:
            raise CitizenPhoneMismatchError("Updated userId does not match.")
        old_key = phone_claim_key(old_phone)
        new_key = phone_claim_key(updated_user.phone)
        with self._lock:
            existing = self._users.get(user_id)
            if existing is None:
                raise CitizenNotFoundError("Citizen not found.")
            if existing.phone != old_phone:
                raise CitizenPhoneMismatchError("Current phone no longer matches.")
            if self._claims.get(old_key) != user_id:
                raise CitizenPhoneMismatchError("Current phone claim no longer matches.")
            if new_key in self._claims and self._claims[new_key] != user_id:
                raise PhoneClaimConflictError("Phone number is already claimed.")

            self._claims[new_key] = user_id
            if old_key != new_key:
                del self._claims[old_key]

            self._users[user_id] = updated_user
            return updated_user

    def anonymize(
        self,
        *,
        user_id: str,
        current_phone: str,
        anonymized_user: StoredCitizenUser,
    ) -> StoredCitizenUser:
        if anonymized_user.user_id != user_id:
            raise CitizenPhoneMismatchError("Updated userId does not match.")
        with self._lock:
            existing = self._users.get(user_id)
            if existing is None:
                raise CitizenNotFoundError("Citizen not found.")
            if existing.phone != current_phone:
                raise CitizenPhoneMismatchError("Current phone no longer matches.")

            # Only release a real E.164 claim. Tombstones never own the claims table.
            if not current_phone.startswith("ANON:"):
                claim_key = phone_claim_key(current_phone)
                if self._claims.get(claim_key) == user_id:
                    del self._claims[claim_key]

            self._users[user_id] = anonymized_user
            return anonymized_user

    def clear(self) -> None:
        with self._lock:
            self._users.clear()
            self._claims.clear()


citizen_store = InMemoryCitizenStore()
