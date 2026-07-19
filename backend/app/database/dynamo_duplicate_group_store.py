from app.config import Settings, get_settings
from app.database.duplicate_group_serialization import (
    duplicate_group_to_item,
    item_to_duplicate_group,
)
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.schemas.stored_duplicate_group import StoredDuplicateGroup


class DynamoDuplicateGroupStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._resource = create_dynamodb_resource(self._settings)
        prefix = self._settings.dynamodb_table_prefix
        self._table = self._resource.Table(build_table_name(prefix, "duplicate-groups"))

    def save(self, group: StoredDuplicateGroup) -> None:
        self._table.put_item(Item=duplicate_group_to_item(group))

    def get(self, duplicate_group_id: str) -> StoredDuplicateGroup | None:
        response = self._table.get_item(Key={"duplicateGroupId": duplicate_group_id})
        item = response.get("Item")
        if not item:
            return None
        return item_to_duplicate_group(item)

    def clear(self) -> None:
        message = "DynamoDuplicateGroupStore does not support clear(). Use db-reset for local dev."
        raise NotImplementedError(message)
