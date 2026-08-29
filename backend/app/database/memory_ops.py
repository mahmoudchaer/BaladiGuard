"""In-memory developer-operator control-plane stores (issue #320)."""

from __future__ import annotations

from threading import Lock

from app.schemas.stored_ops import StoredOpsAlertAck, StoredOpsAudit, StoredOpsErrorGroup


class InMemoryOpsAlertAckStore:
    def __init__(self) -> None:
        self._items: dict[str, StoredOpsAlertAck] = {}
        self._lock = Lock()

    def put(self, entry: StoredOpsAlertAck) -> StoredOpsAlertAck:
        with self._lock:
            stored = entry.model_copy(deep=True)
            self._items[stored.alarm_name] = stored
            return stored.model_copy(deep=True)

    def get(self, alarm_name: str) -> StoredOpsAlertAck | None:
        with self._lock:
            item = self._items.get(alarm_name)
            return item.model_copy(deep=True) if item else None

    def list_all(self) -> list[StoredOpsAlertAck]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self._items.values()]

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


class InMemoryOpsErrorStore:
    def __init__(self) -> None:
        self._items: dict[str, StoredOpsErrorGroup] = {}
        self._lock = Lock()

    def upsert(self, entry: StoredOpsErrorGroup) -> StoredOpsErrorGroup:
        with self._lock:
            existing = self._items.get(entry.error_key)
            if existing is None:
                stored = entry.model_copy(deep=True)
            else:
                stored = existing.model_copy(
                    update={
                        "count": existing.count + entry.count,
                        "last_seen": entry.last_seen,
                        "last_request_id": entry.last_request_id or existing.last_request_id,
                        "last_job_id": entry.last_job_id or existing.last_job_id,
                        "version": entry.version or existing.version,
                    }
                )
            self._items[stored.error_key] = stored
            return stored.model_copy(deep=True)

    def list_recent(self, *, limit: int = 50) -> list[StoredOpsErrorGroup]:
        with self._lock:
            items = [item.model_copy(deep=True) for item in self._items.values()]
        items.sort(key=lambda item: item.last_seen, reverse=True)
        return items[: max(1, min(limit, 200))]

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


class InMemoryOpsAuditStore:
    def __init__(self) -> None:
        self._items: list[StoredOpsAudit] = []
        self._lock = Lock()

    def append(self, entry: StoredOpsAudit) -> None:
        with self._lock:
            self._items.append(entry.model_copy(deep=True))

    def list_recent(self, *, limit: int = 100) -> list[StoredOpsAudit]:
        with self._lock:
            items = [item.model_copy(deep=True) for item in self._items]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items[: max(1, min(limit, 200))]

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


ops_alert_ack_store = InMemoryOpsAlertAckStore()
ops_error_store = InMemoryOpsErrorStore()
ops_audit_store = InMemoryOpsAuditStore()
