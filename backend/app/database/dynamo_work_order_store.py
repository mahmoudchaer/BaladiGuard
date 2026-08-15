"""DynamoDB work-order store (issue #247)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import convert_decimals, prepare_dynamodb_value
from app.database.ticket_patch import build_update_expression
from app.database.work_order_store import (
    WorkOrderTicketMissingError,
    active_work_order_claim_id,
)
from app.schemas.work_order import StoredWorkOrder, is_active_work_order_state

T = TypeVar("T")
_SERIALIZER = TypeSerializer()
_CLAIM_ITEM_TYPE = "ACTIVE_CLAIM"


def _is_claim_item(item: dict[str, Any]) -> bool:
    return item.get("itemType") == _CLAIM_ITEM_TYPE or str(item.get("workOrderId", "")).startswith(
        "wo_active_"
    )


def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: _SERIALIZER.serialize(value) for key, value in item.items()}


def _serialize_values(values: dict[str, Any]) -> dict[str, Any]:
    return {key: _SERIALIZER.serialize(value) for key, value in values.items()}


def _to_wire_transact_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wired: list[dict[str, Any]] = []
    for entry in items:
        action, payload = next(iter(entry.items()))
        converted = dict(payload)
        if "Item" in converted:
            converted["Item"] = _serialize_item(converted["Item"])
        if "Key" in converted:
            converted["Key"] = _serialize_item(converted["Key"])
        if "ExpressionAttributeValues" in converted:
            converted["ExpressionAttributeValues"] = _serialize_values(
                converted["ExpressionAttributeValues"]
            )
        wired.append({action: converted})
    return wired


class DynamoWorkOrderStore:
    def __init__(self, settings: Settings | None = None) -> None:
        resolved = settings or get_settings()
        resource = create_dynamodb_resource(resolved)
        prefix = resolved.dynamodb_table_prefix
        self._table = resource.Table(build_table_name(prefix, "work-orders"))
        self._tickets = resource.Table(build_table_name(prefix, "tickets"))
        self._client = resource.meta.client

    def run_exclusive(self, callback: Callable[[], T]) -> T:
        return callback()

    def save(self, work_order: StoredWorkOrder) -> StoredWorkOrder:
        raise RuntimeError(
            "Use create_active or save_if_state so DynamoDB can enforce work-order invariants."
        )

    def create_active(self, work_order: StoredWorkOrder) -> StoredWorkOrder:
        existing = self.find_active_for_ticket(work_order.ticket_id)
        if existing is not None:
            return existing
        ticket_expression, ticket_names, ticket_values = build_update_expression(
            {
                "active_work_order_id": work_order.work_order_id,
                "updated_at": work_order.updated_at,
                "updated_by": work_order.updated_by,
            }
        )
        items = [
            {
                "Put": {
                    "TableName": self._table.name,
                    "Item": prepare_dynamodb_value(
                        work_order.model_dump(by_alias=True, mode="json")
                    ),
                    "ConditionExpression": "attribute_not_exists(workOrderId)",
                }
            },
            {
                "Put": {
                    "TableName": self._table.name,
                    "Item": {
                        "workOrderId": active_work_order_claim_id(work_order.ticket_id),
                        "itemType": _CLAIM_ITEM_TYPE,
                        "activeWorkOrderId": work_order.work_order_id,
                        "ticketId": work_order.ticket_id,
                    },
                    "ConditionExpression": "attribute_not_exists(workOrderId)",
                }
            },
            {
                "Update": {
                    "TableName": self._tickets.name,
                    "Key": {"ticketId": work_order.ticket_id},
                    "UpdateExpression": ticket_expression,
                    "ConditionExpression": (
                        "attribute_exists(ticketId) AND attribute_not_exists(activeWorkOrderId)"
                    ),
                    "ExpressionAttributeNames": ticket_names,
                    "ExpressionAttributeValues": ticket_values,
                }
            },
        ]
        try:
            self._transact_write(items)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "TransactionCanceledException":
                raise
            raced = self.find_active_for_ticket(work_order.ticket_id)
            if raced is not None:
                return raced
            if self._tickets.get_item(
                Key={"ticketId": work_order.ticket_id}, ConsistentRead=True
            ).get("Item"):
                raced = self.find_active_for_ticket(work_order.ticket_id)
                if raced is not None:
                    return raced
            raise WorkOrderTicketMissingError("Ticket was not found.") from exc
        return work_order

    def save_if_state(
        self,
        work_order: StoredWorkOrder,
        *,
        expected_state: str,
        expected_updated_at: str,
        clear_active: bool = False,
    ) -> StoredWorkOrder | None:
        items: list[dict[str, Any]] = [
            self._work_order_update_item(
                work_order,
                expected_state=expected_state,
                expected_updated_at=expected_updated_at,
            )
        ]
        if clear_active:
            ticket_expression, ticket_names, ticket_values = build_update_expression(
                {
                    "active_work_order_id": None,
                    "updated_at": work_order.updated_at,
                    "updated_by": work_order.updated_by,
                }
            )
            ticket_values[":wo"] = work_order.work_order_id
            items.extend(
                [
                    {
                        "Delete": {
                            "TableName": self._table.name,
                            "Key": {
                                "workOrderId": active_work_order_claim_id(work_order.ticket_id)
                            },
                            "ConditionExpression": "activeWorkOrderId = :wo",
                            "ExpressionAttributeValues": {":wo": work_order.work_order_id},
                        }
                    },
                    {
                        "Update": {
                            "TableName": self._tickets.name,
                            "Key": {"ticketId": work_order.ticket_id},
                            "UpdateExpression": ticket_expression,
                            "ConditionExpression": (
                                "attribute_exists(ticketId) AND ("
                                "activeWorkOrderId = :wo OR "
                                "attribute_not_exists(activeWorkOrderId))"
                            ),
                            "ExpressionAttributeNames": ticket_names,
                            "ExpressionAttributeValues": ticket_values,
                        }
                    },
                ]
            )
        try:
            self._transact_write(items)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "TransactionCanceledException":
                raise
            return None
        return work_order

    def get(self, work_order_id: str) -> StoredWorkOrder | None:
        response = self._table.get_item(Key={"workOrderId": work_order_id}, ConsistentRead=True)
        item = response.get("Item")
        if not item or _is_claim_item(item):
            return None
        return StoredWorkOrder.model_validate(convert_decimals(item))

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredWorkOrder]:
        response = self._table.query(
            IndexName="ticketId-index",
            KeyConditionExpression=Key("ticketId").eq(ticket_id),
        )
        items = [
            StoredWorkOrder.model_validate(convert_decimals(item))
            for item in response.get("Items", [])
            if not _is_claim_item(item)
        ]
        return sorted(items, key=lambda item: (item.created_at, item.work_order_id))

    def find_active_for_ticket(self, ticket_id: str) -> StoredWorkOrder | None:
        claim = self._table.get_item(
            Key={"workOrderId": active_work_order_claim_id(ticket_id)},
            ConsistentRead=True,
        ).get("Item")
        if claim and claim.get("activeWorkOrderId"):
            loaded = self.get(str(claim["activeWorkOrderId"]))
            if loaded is not None and is_active_work_order_state(loaded.state):
                return loaded
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

    def _work_order_update_item(
        self,
        work_order: StoredWorkOrder,
        *,
        expected_state: str,
        expected_updated_at: str,
    ) -> dict[str, Any]:
        dumped = {
            key: value
            for key, value in work_order.model_dump(by_alias=True, mode="json").items()
            if key != "workOrderId" and value is not None
        }
        names = {"#state": "state"}
        values: dict[str, Any] = {
            ":expectedState": expected_state,
            ":expectedUpdatedAt": expected_updated_at,
        }
        set_parts: list[str] = []
        for index, (key, value) in enumerate(dumped.items()):
            name_key = f"#u{index}"
            value_key = f":u{index}"
            names[name_key] = key
            values[value_key] = value
            set_parts.append(f"{name_key} = {value_key}")
        return {
            "Update": {
                "TableName": self._table.name,
                "Key": {"workOrderId": work_order.work_order_id},
                "UpdateExpression": "SET " + ", ".join(set_parts),
                "ConditionExpression": (
                    "attribute_exists(workOrderId) AND #state = :expectedState "
                    "AND updatedAt = :expectedUpdatedAt"
                ),
                "ExpressionAttributeNames": names,
                "ExpressionAttributeValues": values,
            }
        }

    def _transact_write(self, items: list[dict[str, Any]]) -> None:
        try:
            self._client.transact_write_items(TransactItems=_to_wire_transact_items(items))
            return
        except ClientError as error:
            reasons = error.response.get("CancellationReasons") or []
            needs_document = any(
                reason.get("Code") == "TypeError"
                or "serialized" in str(reason.get("Message", "")).lower()
                for reason in reasons
            )
            if not needs_document:
                raise
        self._client.transact_write_items(TransactItems=items)
