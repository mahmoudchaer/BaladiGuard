"""DynamoDB work-order evidence store (issue #248).

Evidence items live in the work-orders table with ``itemType=EVIDENCE`` so no
new table is required. Work-order reads skip these items.
"""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Attr, Key

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import convert_decimals, prepare_dynamodb_value
from app.schemas.work_order_evidence import StoredWorkOrderEvidence, WorkOrderEvidenceKind

EVIDENCE_ITEM_TYPE = "EVIDENCE"


def is_evidence_item(item: dict[str, Any]) -> bool:
    work_order_id = str(item.get("workOrderId", ""))
    return item.get("itemType") == EVIDENCE_ITEM_TYPE or work_order_id.startswith("ev_")


class DynamoWorkOrderEvidenceStore:
    def __init__(self, settings: Settings | None = None) -> None:
        resolved = settings or get_settings()
        resource = create_dynamodb_resource(resolved)
        prefix = resolved.dynamodb_table_prefix
        self._table = resource.Table(build_table_name(prefix, "work-orders"))

    def save(self, evidence: StoredWorkOrderEvidence) -> StoredWorkOrderEvidence:
        item = evidence.model_dump(by_alias=True, mode="json")
        item["workOrderId"] = evidence.evidence_id
        item["parentWorkOrderId"] = evidence.work_order_id
        item["itemType"] = EVIDENCE_ITEM_TYPE
        put_item = {
            "Item": prepare_dynamodb_value(item),
            "ConditionExpression": "attribute_not_exists(workOrderId)",
        }
        if evidence.kind != "AFTER":
            self._table.put_item(**put_item)
            return evidence
        self._table.meta.client.transact_write_items(
            TransactItems=[
                {"Put": {"TableName": self._table.name, **put_item}},
                {
                    "Update": {
                        "TableName": self._table.name,
                        "Key": {"workOrderId": evidence.work_order_id},
                        "UpdateExpression": "ADD afterImageCount :one",
                        "ConditionExpression": "attribute_exists(workOrderId)",
                        "ExpressionAttributeValues": {":one": 1},
                    }
                },
            ]
        )
        return evidence

    def get(self, evidence_id: str) -> StoredWorkOrderEvidence | None:
        response = self._table.get_item(Key={"workOrderId": evidence_id}, ConsistentRead=True)
        item = response.get("Item")
        if not item or not is_evidence_item(item):
            return None
        return _from_item(item)

    def list_by_work_order_id(self, work_order_id: str) -> list[StoredWorkOrderEvidence]:
        parent = self._table.get_item(Key={"workOrderId": work_order_id}, ConsistentRead=True).get(
            "Item"
        )
        ticket_id = str(parent["ticketId"]) if parent and parent.get("ticketId") else None
        if ticket_id:
            return [
                item
                for item in self.list_by_ticket_id(ticket_id)
                if item.work_order_id == work_order_id
            ]
        response = self._table.scan(
            FilterExpression=Attr("itemType").eq(EVIDENCE_ITEM_TYPE)
            & Attr("parentWorkOrderId").eq(work_order_id)
        )
        items = [_from_item(item) for item in response.get("Items", [])]
        return sorted(items, key=lambda item: (item.created_at, item.evidence_id))

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredWorkOrderEvidence]:
        items: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {
            "IndexName": "ticketId-index",
            "KeyConditionExpression": Key("ticketId").eq(ticket_id),
        }
        while True:
            response = self._table.query(**kwargs)
            items.extend(response.get("Items") or [])
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
        evidence = [_from_item(item) for item in items if is_evidence_item(item)]
        return sorted(evidence, key=lambda item: (item.created_at, item.evidence_id))

    def find_original_for_work_order(self, work_order_id: str) -> StoredWorkOrderEvidence | None:
        for item in self.list_by_work_order_id(work_order_id):
            if item.kind == "ORIGINAL_REPORT":
                return item
        return None

    def count_by_kind(self, work_order_id: str, kind: WorkOrderEvidenceKind) -> int:
        return sum(1 for item in self.list_by_work_order_id(work_order_id) if item.kind == kind)

    def clear(self) -> None:
        raise NotImplementedError("DynamoWorkOrderEvidenceStore does not support clear().")


def _from_item(item: dict[str, Any]) -> StoredWorkOrderEvidence:
    payload = convert_decimals(item)
    payload["evidenceId"] = payload.get("evidenceId") or payload.get("workOrderId")
    payload["workOrderId"] = payload.get("parentWorkOrderId") or payload.get("workOrderId")
    return StoredWorkOrderEvidence.model_validate(payload)
