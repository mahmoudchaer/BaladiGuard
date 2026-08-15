"""DynamoDB work-order store (issue #247)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from boto3.dynamodb.conditions import Key

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import convert_decimals, prepare_dynamodb_value
from app.schemas.work_order import StoredWorkOrder, is_active_work_order_state

T = TypeVar("T")


class DynamoWorkOrderStore:
    def __init__(self, settings: Settings | None = None) -> None:
        resolved = settings or get_settings()
        resource = create_dynamodb_resource(resolved)
        self._table = resource.Table(
            build_table_name(resolved.dynamodb_table_prefix, "work-orders")
        )

    def run_exclusive(self, callback: Callable[[], T]) -> T:
        return callback()

    def save(self, work_order: StoredWorkOrder) -> StoredWorkOrder:
        self._table.put_item(
            Item=prepare_dynamodb_value(work_order.model_dump(by_alias=True, mode="json"))
        )
        return work_order

    def get(self, work_order_id: str) -> StoredWorkOrder | None:
        response = self._table.get_item(Key={"workOrderId": work_order_id}, ConsistentRead=True)
        item = response.get("Item")
        return StoredWorkOrder.model_validate(convert_decimals(item)) if item else None

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredWorkOrder]:
        response = self._table.query(
            IndexName="ticketId-index",
            KeyConditionExpression=Key("ticketId").eq(ticket_id),
        )
        items = [
            StoredWorkOrder.model_validate(convert_decimals(item))
            for item in response.get("Items", [])
        ]
        return sorted(items, key=lambda item: (item.created_at, item.work_order_id))

    def find_active_for_ticket(self, ticket_id: str) -> StoredWorkOrder | None:
        active = [
            item
            for item in self.list_by_ticket_id(ticket_id)
            if is_active_work_order_state(item.state)
        ]
        if not active:
            return None
        return sorted(active, key=lambda item: (item.created_at, item.work_order_id))[0]

    def clear(self) -> None:
        raise NotImplementedError("DynamoWorkOrderStore does not support clear().")
