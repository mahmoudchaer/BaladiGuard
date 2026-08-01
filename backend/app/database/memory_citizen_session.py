"""In-memory citizen session store (issue #169)."""

from __future__ import annotations

from threading import Lock

from app.schemas.citizen_session import StoredCitizenSession


class InMemoryCitizenSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, StoredCitizenSession] = {}
        self._lock = Lock()

    def create(self, session: StoredCitizenSession) -> StoredCitizenSession:
        with self._lock:
            self._sessions[session.session_id] = session
            return session

    def get(self, session_id: str) -> StoredCitizenSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def revoke(
        self,
        session_id: str,
        *,
        revoked_at: str,
        reason: str,
    ) -> StoredCitizenSession | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.revoked_at is not None:
                return session
            updated = session.model_copy(update={"revoked_at": revoked_at, "revoke_reason": reason})
            self._sessions[session_id] = updated
            return updated

    def revoke_all_for_user(
        self,
        user_id: str,
        *,
        revoked_at: str,
        reason: str,
    ) -> int:
        with self._lock:
            count = 0
            for session_id, session in list(self._sessions.items()):
                if session.user_id != user_id or session.revoked_at is not None:
                    continue
                self._sessions[session_id] = session.model_copy(
                    update={"revoked_at": revoked_at, "revoke_reason": reason}
                )
                count += 1
            return count

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()


citizen_session_store = InMemoryCitizenSessionStore()
