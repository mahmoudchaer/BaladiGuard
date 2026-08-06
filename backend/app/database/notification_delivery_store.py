"""Notification delivery attempt store protocol (issue #183)."""

from __future__ import annotations

from typing import Protocol

from app.schemas.stored_notification_delivery import StoredNotificationDelivery


class NotificationDeliveryStore(Protocol):
    def append(self, entry: StoredNotificationDelivery) -> None: ...

    def list_by_idempotency_key(self, key: str) -> list[StoredNotificationDelivery]: ...

    def clear(self) -> None: ...
