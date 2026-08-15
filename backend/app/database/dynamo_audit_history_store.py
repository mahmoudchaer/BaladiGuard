from boto3.dynamodb.conditions import Key

from app.config import Settings, get_settings
from app.database.audit_history_serialization import audit_history_to_item, item_to_audit_history
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.schemas.stored_audit_history import StoredAuditHistory


class DynamoAuditHistoryStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._resource = create_dynamodb_resource(self._settings)
        prefix = self._settings.dynamodb_table_prefix
        self._table = self._resource.Table(build_table_name(prefix, "ticket-audit-history"))

    def append(self, entry: StoredAuditHistory) -> None:
        self._table.put_item(Item=audit_history_to_item(entry))

    def list_by_ticket_id_page(
        self, ticket_id: str, *, limit: int, exclusive_start_key: dict | None = None
    ) -> tuple[list[StoredAuditHistory], dict | None]:
        query_kwargs = {
            "IndexName": "ticketId-index",
            "KeyConditionExpression": Key("ticketId").eq(ticket_id),
            "Limit": limit,
        }
        if exclusive_start_key:
            query_kwargs["ExclusiveStartKey"] = exclusive_start_key
        response = self._table.query(**query_kwargs)
        return (
            [item_to_audit_history(item) for item in response.get("Items", [])],
            response.get("LastEvaluatedKey"),
        )

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredAuditHistory]:
        entries = []
        query_kwargs = {
            "IndexName": "ticketId-index",
            "KeyConditionExpression": Key("ticketId").eq(ticket_id),
        }
        while True:
            response = self._table.query(**query_kwargs)
            entries.extend(item_to_audit_history(item) for item in response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key
        return sorted(entries, key=lambda entry: entry.created_at)

    def clear(self) -> None:
        message = "DynamoAuditHistoryStore does not support clear(). Use db-reset for local dev."
        raise NotImplementedError(message)
