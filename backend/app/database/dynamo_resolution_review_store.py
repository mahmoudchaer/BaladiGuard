"""DynamoDB resolution-feedback review queue (issue #248).

Review-queue items live in the work-orders table with ``itemType=RESOLUTION_REVIEW``.
"""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Attr

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import convert_decimals, prepare_dynamodb_value
from app.schemas.resolution_feedback import StoredResolutionReview

REVIEW_ITEM_TYPE = "RESOLUTION_REVIEW"
REVIEW_ID_PREFIX = "rr_"


def review_item_id(ticket_id: str) -> str:
    return f"{REVIEW_ID_PREFIX}{ticket_id}"


def is_review_item(item: dict[str, Any]) -> bool:
    return item.get("itemType") == REVIEW_ITEM_TYPE or str(item.get("workOrderId", "")).startswith(
        REVIEW_ID_PREFIX
    )


class DynamoResolutionReviewStore:
    def __init__(self, settings: Settings | None = None) -> None:
        resolved = settings or get_settings()
        resource = create_dynamodb_resource(resolved)
        prefix = resolved.dynamodb_table_prefix
        self._table = resource.Table(build_table_name(prefix, "work-orders"))

    def save(self, review: StoredResolutionReview) -> StoredResolutionReview:
        item = review.model_dump(by_alias=True, mode="json")
        item["workOrderId"] = review_item_id(review.ticket_id)
        item["itemType"] = REVIEW_ITEM_TYPE
        self._table.put_item(Item=prepare_dynamodb_value(item))
        return review

    def get_by_ticket_id(self, ticket_id: str) -> StoredResolutionReview | None:
        response = self._table.get_item(
            Key={"workOrderId": review_item_id(ticket_id)}, ConsistentRead=True
        )
        item = response.get("Item")
        if not item or not is_review_item(item):
            return None
        return StoredResolutionReview.model_validate(convert_decimals(item))

    def list_pending(self, *, municipality_id: str | None) -> list[StoredResolutionReview]:
        expression = Attr("itemType").eq(REVIEW_ITEM_TYPE) & Attr("reviewStatus").eq("PENDING")
        if municipality_id:
            expression = expression & Attr("municipalityId").eq(municipality_id)
        response = self._table.scan(FilterExpression=expression)
        items = [
            StoredResolutionReview.model_validate(convert_decimals(item))
            for item in response.get("Items", [])
        ]
        return sorted(items, key=lambda item: (item.submitted_at, item.ticket_id), reverse=True)

    def delete(self, ticket_id: str) -> None:
        self._table.delete_item(Key={"workOrderId": review_item_id(ticket_id)})

    def clear(self) -> None:
        raise NotImplementedError("DynamoResolutionReviewStore does not support clear().")
