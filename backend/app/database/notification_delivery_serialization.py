from typing import Any

from app.schemas.stored_notification_delivery import StoredNotificationDelivery


def notification_delivery_to_item(entry: StoredNotificationDelivery) -> dict[str, Any]:
    return entry.model_dump(by_alias=True, mode="json")


def item_to_notification_delivery(item: dict[str, Any]) -> StoredNotificationDelivery:
    return StoredNotificationDelivery.model_validate(item)
