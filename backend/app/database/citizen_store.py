"""Citizen account store protocol (issue #169)."""

from __future__ import annotations

from typing import Protocol

from app.schemas.citizen import StoredCitizenUser


class PhoneClaimConflictError(Exception):
    """Raised when a canonical phone is already claimed by another citizen."""


class CitizenNotFoundError(Exception):
    """Raised when a citizen userId does not exist."""


class CitizenPhoneMismatchError(Exception):
    """Raised when a phone-change condition no longer matches the stored phone."""


class CitizenStore(Protocol):
    def create(self, user: StoredCitizenUser) -> StoredCitizenUser:
        """Create a citizen and claim their phone atomically."""

    def get(self, user_id: str) -> StoredCitizenUser | None: ...

    def get_by_phone(self, canonical_phone: str) -> StoredCitizenUser | None: ...

    def update(self, user: StoredCitizenUser) -> StoredCitizenUser:
        """Replace mutable profile fields for an existing citizen."""

    def change_phone(
        self,
        *,
        user_id: str,
        old_phone: str,
        new_phone: str,
        phone_verified_at: str,
        updated_at: str,
    ) -> StoredCitizenUser:
        """Atomically transfer the phone claim and update the citizen record."""

    def clear(self) -> None: ...
