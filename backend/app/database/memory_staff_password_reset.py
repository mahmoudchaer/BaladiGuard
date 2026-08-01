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

    def consume(
        self,
        challenge_id: str,
        *,
        consumed_at: str,
        expected_attempt_count: int,
    ) -> StoredStaffPasswordResetChallenge | None:
        """Atomically consume a live challenge; returns None if already spent."""
        with self._lock:
            existing = self._challenges.get(challenge_id)
            if (
                existing is None
                or existing.consumed_at
                or existing.superseded_at
                or existing.attempt_count != expected_attempt_count
            ):
                return None
            updated = existing.model_copy(
                update={
                    "consumed_at": consumed_at,
                    "attempt_count": existing.attempt_count + 1,
                }
            )
            self._challenges[challenge_id] = updated
            return updated

    def increment_attempt(self, challenge_id: str) -> StoredStaffPasswordResetChallenge | None:
        """Atomically bump attemptCount while the challenge is still live."""
        with self._lock:
            existing = self._challenges.get(challenge_id)
            if existing is None or existing.consumed_at or existing.superseded_at:
                return None
            updated = existing.model_copy(update={"attempt_count": existing.attempt_count + 1})
            self._challenges[challenge_id] = updated
            return updated

    def clear(self) -> None:
        with self._lock:
            self._challenges.clear()


staff_password_reset_store = InMemoryStaffPasswordResetStore()
