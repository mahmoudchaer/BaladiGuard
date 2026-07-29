"""Best-effort delivery ledger to avoid duplicate notifications (issue #39).

Process-local by default. Sufficient for single-process local/CI and for retries
that re-enter the same API process after a successful emit. Multi-instance Dynamo
dedupe can replace this later without changing callers.
"""

from __future__ import annotations

from threading import Lock
from typing import Protocol


class NotificationDeliveryLedger(Protocol):
    def claim(self, key: str) -> bool:
        """Return True the first time ``key`` is claimed; False for duplicates."""


class InMemoryNotificationDeliveryLedger:
    def __init__(self) -> None:
        self._keys: set[str] = set()
        self._lock = Lock()

    def claim(self, key: str) -> bool:
        normalized = key.strip()
        if not normalized:
            return True
        with self._lock:
            if normalized in self._keys:
                return False
            self._keys.add(normalized)
            return True

    def release(self, key: str) -> None:
        """Allow a later retry after a failed delivery attempt."""
        normalized = key.strip()
        if not normalized:
            return
        with self._lock:
            self._keys.discard(normalized)

    def clear(self) -> None:
        with self._lock:
            self._keys.clear()


_ledger = InMemoryNotificationDeliveryLedger()


def get_delivery_ledger() -> InMemoryNotificationDeliveryLedger:
    return _ledger


def reset_delivery_ledger() -> None:
    """Test helper: clear claimed notification keys between cases."""
    _ledger.clear()


def notification_idempotency_key(
    *,
    event: str,
    ticket_id: str,
    status: str,
) -> str:
    return f"{event}:{ticket_id.strip()}:{status.strip()}"
