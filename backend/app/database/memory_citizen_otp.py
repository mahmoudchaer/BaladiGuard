"""In-memory citizen OTP challenge store (issue #169 phone-change foundation)."""

from __future__ import annotations

from threading import Lock

from app.schemas.citizen_session import StoredCitizenOtpChallenge


class InMemoryCitizenOtpStore:
    def __init__(self) -> None:
        self._challenges: dict[str, StoredCitizenOtpChallenge] = {}
        self._lock = Lock()

    def create(self, challenge: StoredCitizenOtpChallenge) -> StoredCitizenOtpChallenge:
        with self._lock:
            # Resend invalidates prior live codes for the same phone+purpose(+user).
            for existing_id, existing in list(self._challenges.items()):
                if existing.consumed_at or existing.superseded_at:
                    continue
                if existing.phone != challenge.phone or existing.purpose != challenge.purpose:
                    continue
                if existing.user_id != challenge.user_id:
                    continue
                self._challenges[existing_id] = existing.model_copy(
                    update={"superseded_at": challenge.created_at}
                )
            self._challenges[challenge.challenge_id] = challenge
            return challenge

    def get(self, challenge_id: str) -> StoredCitizenOtpChallenge | None:
        with self._lock:
            return self._challenges.get(challenge_id)

    def save(self, challenge: StoredCitizenOtpChallenge) -> StoredCitizenOtpChallenge:
        with self._lock:
            self._challenges[challenge.challenge_id] = challenge
            return challenge

    def consume(
        self,
        challenge_id: str,
        *,
        consumed_at: str,
    ) -> StoredCitizenOtpChallenge | None:
        """Atomically consume a live challenge; returns None if already spent."""
        with self._lock:
            existing = self._challenges.get(challenge_id)
            if existing is None or existing.consumed_at or existing.superseded_at:
                return None
            updated = existing.model_copy(
                update={
                    "consumed_at": consumed_at,
                    "attempt_count": existing.attempt_count + 1,
                }
            )
            self._challenges[challenge_id] = updated
            return updated

    def increment_attempt(self, challenge_id: str) -> StoredCitizenOtpChallenge | None:
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


citizen_otp_store = InMemoryCitizenOtpStore()
