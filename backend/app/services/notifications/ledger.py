"""Delivery ledger to avoid duplicate notifications (issues #39 / #183).

Memory backend keeps claims process-local (sufficient for single-process local/CI).
DynamoDB backend uses a conditional put on ``notification-claims`` so multi-instance
workers cannot both deliver the same event/ticket/status notification.
"""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from typing import Protocol

from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name


class NotificationDeliveryLedger(Protocol):
    def claim(self, key: str) -> bool:
        """Return True the first time ``key`` is claimed; False for duplicates."""

    def release(self, key: str) -> None:
        """Allow a later retry after a failed delivery attempt."""


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


class DynamoNotificationDeliveryLedger:
    """Durable idempotency claims via conditional DynamoDB puts."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._resource = create_dynamodb_resource(self._settings)
        prefix = self._settings.dynamodb_table_prefix
        self._table = self._resource.Table(build_table_name(prefix, "notification-claims"))

    def claim(self, key: str) -> bool:
        normalized = key.strip()
        if not normalized:
            return True
        try:
            self._table.put_item(
                Item={
                    "idempotencyKey": normalized,
                    "claimedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                },
                ConditionExpression="attribute_not_exists(idempotencyKey)",
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise
        return True

    def release(self, key: str) -> None:
        normalized = key.strip()
        if not normalized:
            return
        self._table.delete_item(Key={"idempotencyKey": normalized})


_ledger = InMemoryNotificationDeliveryLedger()


def get_delivery_ledger(settings: Settings | None = None) -> NotificationDeliveryLedger:
    resolved = settings or get_settings()
    if resolved.use_dynamodb:
        return DynamoNotificationDeliveryLedger(resolved)
    return _ledger


def reset_delivery_ledger() -> None:
    """Test helper: clear claimed notification keys between cases (memory only)."""
    _ledger.clear()


def notification_idempotency_key(
    *,
    event: str,
    ticket_id: str,
    status: str,
) -> str:
    return f"{event}:{ticket_id.strip()}:{status.strip()}"
