"""DynamoDB developer-operator control-plane stores (issue #320)."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.schemas.stored_ops import StoredOpsAlertAck, StoredOpsAudit, StoredOpsErrorGroup


class DynamoOpsAlertAckStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        resource = create_dynamodb_resource(self._settings)
        self._table = resource.Table(
            build_table_name(self._settings.dynamodb_table_prefix, "ops-alert-acks")
        )

    def put(self, entry: StoredOpsAlertAck) -> StoredOpsAlertAck:
        self._table.put_item(Item=entry.model_dump(by_alias=True, exclude_none=True))
        return entry

    def get(self, alarm_name: str) -> StoredOpsAlertAck | None:
        response = self._table.get_item(Key={"alarmName": alarm_name})
        item = response.get("Item")
        return StoredOpsAlertAck.model_validate(item) if item else None

    def list_all(self) -> list[StoredOpsAlertAck]:
        items: list[StoredOpsAlertAck] = []
        start = None
        pages = 0
        while pages < 3:
            kwargs: dict[str, Any] = {"Limit": 100}
            if start:
                kwargs["ExclusiveStartKey"] = start
            response = self._table.scan(**kwargs)
            items.extend(
                StoredOpsAlertAck.model_validate(item) for item in response.get("Items", [])
            )
            pages += 1
            start = response.get("LastEvaluatedKey")
            if not start or len(items) >= 200:
                return items[:200]
        return items[:200]

    def clear(self) -> None:
        raise NotImplementedError("Use db-reset for DynamoDB-backed ops stores.")


class DynamoOpsErrorStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        resource = create_dynamodb_resource(self._settings)
        self._table = resource.Table(
            build_table_name(self._settings.dynamodb_table_prefix, "ops-error-groups")
        )

    def upsert(self, entry: StoredOpsErrorGroup) -> StoredOpsErrorGroup:
        existing = self._table.get_item(Key={"errorKey": entry.error_key}).get("Item")
        if existing is None:
            stored = entry
        else:
            current = StoredOpsErrorGroup.model_validate(existing)
            stored = current.model_copy(
                update={
                    "count": current.count + entry.count,
                    "last_seen": entry.last_seen,
                    "last_request_id": entry.last_request_id or current.last_request_id,
                    "last_job_id": entry.last_job_id or current.last_job_id,
                    "version": entry.version or current.version,
                }
            )
        self._table.put_item(Item=stored.model_dump(by_alias=True, exclude_none=True))
        return stored

    def list_recent(self, *, limit: int = 50) -> list[StoredOpsErrorGroup]:
        response = self._table.scan(Limit=200)
        items = [StoredOpsErrorGroup.model_validate(item) for item in response.get("Items", [])]
        items.sort(key=lambda item: item.last_seen, reverse=True)
        return items[: max(1, min(limit, 200))]

    def clear(self) -> None:
        raise NotImplementedError("Use db-reset for DynamoDB-backed ops stores.")


class DynamoOpsAuditStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        resource = create_dynamodb_resource(self._settings)
        self._table = resource.Table(
            build_table_name(self._settings.dynamodb_table_prefix, "ops-audit")
        )

    def append(self, entry: StoredOpsAudit) -> None:
        self._table.put_item(Item=entry.model_dump(by_alias=True, exclude_none=True))

    def list_recent(self, *, limit: int = 100) -> list[StoredOpsAudit]:
        response = self._table.scan(Limit=200)
        items = [StoredOpsAudit.model_validate(item) for item in response.get("Items", [])]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items[: max(1, min(limit, 200))]

    def clear(self) -> None:
        raise NotImplementedError("Use db-reset for DynamoDB-backed ops stores.")
