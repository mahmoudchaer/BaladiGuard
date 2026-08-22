"""DynamoDB contribution ledger and ranking projection (issue #323)."""

from __future__ import annotations

import logging

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.schemas.stored_rewards import StoredRewardEvent, StoredRewardProjection

logger = logging.getLogger(__name__)


def _is_missing_table(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") == "ResourceNotFoundException"


def _is_condition_failed(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


class DynamoRewardsLedgerStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        resource = create_dynamodb_resource(self._settings)
        self._table = resource.Table(
            build_table_name(self._settings.dynamodb_table_prefix, "rewards-ledger")
        )

    def get_by_event_key(self, event_key: str) -> StoredRewardEvent | None:
        try:
            response = self._table.query(
                IndexName="eventKey-index",
                KeyConditionExpression=Key("eventKey").eq(event_key),
                Limit=1,
            )
        except ClientError as error:
            if _is_missing_table(error):
                logger.warning("Rewards ledger table is missing; treating event as absent.")
                return None
            raise
        items = response.get("Items") or []
        if not items:
            return None
        return StoredRewardEvent.model_validate(items[0])

    def put_if_absent(self, event: StoredRewardEvent) -> StoredRewardEvent:
        item = event.model_dump(by_alias=True, exclude_none=True)
        try:
            self._table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(eventKey)",
            )
            return event
        except ClientError as error:
            if _is_condition_failed(error):
                existing = self.get_by_event_key(event.event_key)
                if existing is not None:
                    return existing
            if _is_missing_table(error):
                logger.warning("Rewards ledger table is missing; award was not persisted.")
                return event
            raise

    def list_by_citizen(self, citizen_user_id: str) -> list[StoredRewardEvent]:
        try:
            response = self._table.query(
                KeyConditionExpression=Key("citizenUserId").eq(citizen_user_id)
            )
        except ClientError as error:
            if _is_missing_table(error):
                return []
            raise
        items = [StoredRewardEvent.model_validate(item) for item in response.get("Items", [])]
        items.sort(key=lambda item: (item.created_at, item.event_id))
        return items

    def list_by_ticket(self, ticket_id: str) -> list[StoredRewardEvent]:
        try:
            response = self._table.query(
                IndexName="ticketId-index",
                KeyConditionExpression=Key("ticketId").eq(ticket_id),
            )
        except ClientError as error:
            if _is_missing_table(error):
                return []
            raise
        items = [StoredRewardEvent.model_validate(item) for item in response.get("Items", [])]
        items.sort(key=lambda item: (item.created_at, item.event_id))
        return items

    def clear(self) -> None:
        raise NotImplementedError("Use db-reset for DynamoDB-backed rewards stores.")


class DynamoRewardsProjectionStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        resource = create_dynamodb_resource(self._settings)
        self._table = resource.Table(
            build_table_name(self._settings.dynamodb_table_prefix, "rewards-projection")
        )

    def get(self, citizen_user_id: str) -> StoredRewardProjection | None:
        try:
            response = self._table.get_item(Key={"citizenUserId": citizen_user_id})
        except ClientError as error:
            if _is_missing_table(error):
                return None
            raise
        item = response.get("Item")
        return StoredRewardProjection.model_validate(item) if item else None

    def save(self, projection: StoredRewardProjection) -> None:
        try:
            self._table.put_item(Item=projection.model_dump(by_alias=True, exclude_none=True))
        except ClientError as error:
            if _is_missing_table(error):
                logger.warning("Rewards projection table is missing; snapshot was not persisted.")
                return
            raise

    def list_ranked(
        self, *, public_only: bool, period: str, period_key: str
    ) -> list[StoredRewardProjection]:
        if public_only:
            board_key = "public" if period != "monthly" else f"public#{period_key}"
            index = "publicAllTime-index" if period != "monthly" else "publicMonthly-index"
            key_name = "publicBoardKey" if period != "monthly" else "monthlyBoardKey"
            try:
                response = self._table.query(
                    IndexName=index,
                    KeyConditionExpression=Key(key_name).eq(board_key),
                    ScanIndexForward=True,
                )
            except ClientError as error:
                if _is_missing_table(error):
                    return []
                logger.warning("Rewards public index query failed; falling back to scan.")
                return self._scan_ranked(public_only=True, period=period, period_key=period_key)
            items = [
                StoredRewardProjection.model_validate(item) for item in response.get("Items", [])
            ]
            sort_attr = "all_time_sort_key" if period != "monthly" else "monthly_sort_key"
            items.sort(key=lambda item: getattr(item, sort_attr))
            return [item for item in items if not item.withdrawn and item.public_eligible]
        return self._scan_ranked(public_only=False, period=period, period_key=period_key)

    def _scan_ranked(
        self, *, public_only: bool, period: str, period_key: str
    ) -> list[StoredRewardProjection]:
        try:
            kwargs: dict = {}
            if public_only:
                kwargs["FilterExpression"] = Attr("publicEligible").eq(True) & Attr("withdrawn").eq(
                    False
                )
            response = self._table.scan(**kwargs)
        except ClientError as error:
            if _is_missing_table(error):
                return []
            raise
        items = [StoredRewardProjection.model_validate(item) for item in response.get("Items", [])]
        ranked: list[StoredRewardProjection] = []
        for item in items:
            if item.withdrawn:
                continue
            points = item.confirmed_points_all_time
            if period == "monthly":
                points = (
                    item.confirmed_points_monthly if item.monthly_period_key == period_key else 0
                )
            if points <= 0:
                continue
            if public_only and not item.public_eligible:
                continue
            ranked.append(item)
        if period == "monthly":
            ranked.sort(
                key=lambda item: (
                    -item.confirmed_points_monthly,
                    item.first_award_at or "9999",
                    item.citizen_user_id,
                )
            )
        else:
            ranked.sort(
                key=lambda item: (
                    -item.confirmed_points_all_time,
                    item.first_award_at or "9999",
                    item.citizen_user_id,
                )
            )
        return ranked

    def list_all(self) -> list[StoredRewardProjection]:
        try:
            response = self._table.scan()
        except ClientError as error:
            if _is_missing_table(error):
                return []
            raise
        return [StoredRewardProjection.model_validate(item) for item in response.get("Items", [])]

    def clear(self) -> None:
        raise NotImplementedError("Use db-reset for DynamoDB-backed rewards stores.")
