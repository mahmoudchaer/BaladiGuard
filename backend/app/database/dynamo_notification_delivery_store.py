from boto3.dynamodb.conditions import Key

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.notification_delivery_serialization import (
    item_to_notification_delivery,
    notification_delivery_to_item,
)
from app.schemas.stored_notification_delivery import StoredNotificationDelivery


class DynamoNotificationDeliveryStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._resource = create_dynamodb_resource(self._settings)
        prefix = self._settings.dynamodb_table_prefix
        self._table = self._resource.Table(build_table_name(prefix, "notification-deliveries"))

    def append(self, entry: StoredNotificationDelivery) -> None:
        self._table.put_item(Item=notification_delivery_to_item(entry))

    def list_by_idempotency_key(self, key: str) -> list[StoredNotificationDelivery]:
        response = self._table.query(
            IndexName="idempotencyKey-index",
            KeyConditionExpression=Key("idempotencyKey").eq(key),
        )
        return [item_to_notification_delivery(item) for item in response.get("Items", [])]

    def clear(self) -> None:
        message = (
            "DynamoNotificationDeliveryStore does not support clear(). Use db-reset for local dev."
        )
        raise NotImplementedError(message)
