from app.schemas.stored_notification_delivery import StoredNotificationDelivery


class InMemoryNotificationDeliveryStore:
    def __init__(self) -> None:
        self._entries: list[StoredNotificationDelivery] = []

    def append(self, entry: StoredNotificationDelivery) -> None:
        self._entries.append(entry)

    def list_by_idempotency_key(self, key: str) -> list[StoredNotificationDelivery]:
        return [entry for entry in self._entries if entry.idempotency_key == key]

    def list_all(self) -> list[StoredNotificationDelivery]:
        return list(self._entries)

    def list_recent(self, *, limit: int = 100) -> list[StoredNotificationDelivery]:
        return list(self._entries[-max(1, min(limit, 200)) :])

    def clear(self) -> None:
        self._entries.clear()


notification_delivery_store = InMemoryNotificationDeliveryStore()
