"""In-memory privacy-request audit store (issue #321)."""

from __future__ import annotations

from threading import Lock

from app.schemas.stored_privacy_request import StoredPrivacyRequestAudit


class InMemoryPrivacyRequestAuditStore:
    def __init__(self) -> None:
        self._items: list[StoredPrivacyRequestAudit] = []
        self._lock = Lock()

    def append(self, entry: StoredPrivacyRequestAudit) -> None:
        with self._lock:
            self._items.append(entry.model_copy(deep=True))

    def list_recent(self, *, limit: int = 100) -> list[StoredPrivacyRequestAudit]:
        with self._lock:
            items = [item.model_copy(deep=True) for item in self._items]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items[: max(1, min(limit, 200))]

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


privacy_request_audit_store = InMemoryPrivacyRequestAuditStore()
