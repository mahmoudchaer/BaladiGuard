"""In-memory staff password-reset challenge store (issue #178)."""

from __future__ import annotations

from threading import Lock

from app.schemas.staff_password_reset import StoredStaffPasswordResetChallenge


class InMemoryStaffPasswordResetStore:
    def __init__(self) -> None:
        self._challenges: dict[str, StoredStaffPasswordResetChallenge] = {}
        self._lock = Lock()

    def create(
        self, challenge: StoredStaffPasswordResetChallenge
    ) -> StoredStaffPasswordResetChallenge:
        with self._lock:
            for existing_id, existing in list(self._challenges.items()):
                if existing.consumed_at or existing.superseded_at:
                    continue
                if existing.staff_id != challenge.staff_id:
                    continue
                self._challenges[existing_id] = existing.model_copy(
                    update={"superseded_at": challenge.created_at}
                )
            self._challenges[challenge.challenge_id] = challenge
            return challenge

    def get(self, challenge_id: str) -> StoredStaffPasswordResetChallenge | None:
        with self._lock:
            return self._challenges.get(challenge_id)

    def get_latest_for_username(self, username: str) -> StoredStaffPasswordResetChallenge | None:
        normalized = username.strip().lower()
        with self._lock:
            matches = [
                challenge
                for challenge in self._challenges.values()
                if challenge.username == normalized
                and challenge.consumed_at is None
                and challenge.superseded_at is None
            ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def save(
        self, challenge: StoredStaffPasswordResetChallenge
    ) -> StoredStaffPasswordResetChallenge:
        with self._lock:
            self._challenges[challenge.challenge_id] = challenge
            return challenge

    def clear(self) -> None:
        with self._lock:
            self._challenges.clear()


staff_password_reset_store = InMemoryStaffPasswordResetStore()
