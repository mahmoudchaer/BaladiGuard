from boto3.dynamodb.conditions import Key

from app.config import Settings, get_settings
from app.database.account_audit_serialization import (
    account_audit_to_item,
    item_to_account_audit,
)
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.schemas.stored_account_audit import StoredAccountAudit


class DynamoAccountAuditStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._resource = create_dynamodb_resource(self._settings)
        prefix = self._settings.dynamodb_table_prefix
        self._table = self._resource.Table(build_table_name(prefix, "account-audit"))

    def append(self, entry: StoredAccountAudit) -> None:
        self._table.put_item(Item=account_audit_to_item(entry))

    def list_by_target_staff_id(self, target_staff_id: str) -> list[StoredAccountAudit]:
        response = self._table.query(
            IndexName="targetStaffId-index",
            KeyConditionExpression=Key("targetStaffId").eq(target_staff_id),
        )
        entries = [item_to_account_audit(item) for item in response.get("Items", [])]
        return sorted(entries, key=lambda entry: entry.created_at)

    def list_all(self) -> list[StoredAccountAudit]:
        response = self._table.scan()
        entries = [item_to_account_audit(item) for item in response.get("Items", [])]
        return sorted(entries, key=lambda entry: entry.created_at)

    def clear(self) -> None:
        message = "DynamoAccountAuditStore does not support clear(). Use db-reset for local dev."
        raise NotImplementedError(message)
