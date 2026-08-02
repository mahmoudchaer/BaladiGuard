"""DynamoDB staff password-reset challenge store (issue #178)."""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import convert_decimals, prepare_dynamodb_value
from app.schemas.staff_password_reset import StoredStaffPasswordResetChallenge

_LIVE_CHALLENGE_CONDITION = (
    "attribute_exists(challengeId) AND "
    "attribute_not_exists(consumedAt) AND "
    "attribute_not_exists(supersededAt)"
)


def _to_item(challenge: StoredStaffPasswordResetChallenge) -> dict[str, Any]:
    item = challenge.model_dump(by_alias=True, mode="json")
    filtered = {key: value for key, value in item.items() if value is not None}
    return prepare_dynamodb_value(filtered)


def _from_item(item: dict[str, Any]) -> StoredStaffPasswordResetChallenge:
    return StoredStaffPasswordResetChallenge.model_validate(convert_decimals(item))


class DynamoStaffPasswordResetStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._resource = create_dynamodb_resource(self._settings)
        prefix = self._settings.dynamodb_table_prefix
        self._table = self._resource.Table(
            build_table_name(prefix, "staff-password-reset-challenges")
        )

    def create(
        self, challenge: StoredStaffPasswordResetChallenge
    ) -> StoredStaffPasswordResetChallenge:
        scan_kwargs: dict[str, object] = {
            "FilterExpression": (
                Attr("staffId").eq(challenge.staff_id)
                & Attr("consumedAt").not_exists()
                & Attr("supersededAt").not_exists()
            ),
        }
        while True:
            response = self._table.scan(**scan_kwargs)
            for item in response.get("Items", []):
                existing = _from_item(item)
                self._table.update_item(
                    Key={"challengeId": existing.challenge_id},
                    UpdateExpression="SET supersededAt = :at",
                    ConditionExpression=(
                        "attribute_not_exists(consumedAt) AND attribute_not_exists(supersededAt)"
                    ),
                    ExpressionAttributeValues={":at": challenge.created_at},
                )
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key

        self._table.put_item(Item=_to_item(challenge))
        return challenge

    def get(self, challenge_id: str) -> StoredStaffPasswordResetChallenge | None:
        response = self._table.get_item(Key={"challengeId": challenge_id})
        item = response.get("Item")
        if not item:
            return None
        return _from_item(item)

    def get_latest_for_username(self, username: str) -> StoredStaffPasswordResetChallenge | None:
        normalized = username.strip().lower()
        matches: list[StoredStaffPasswordResetChallenge] = []
        scan_kwargs: dict[str, object] = {
            "FilterExpression": (
                Attr("username").eq(normalized)
                & Attr("consumedAt").not_exists()
                & Attr("supersededAt").not_exists()
            ),
        }
        while True:
            response = self._table.scan(**scan_kwargs)
            matches.extend(_from_item(item) for item in response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def save(
        self, challenge: StoredStaffPasswordResetChallenge
    ) -> StoredStaffPasswordResetChallenge:
        self._table.put_item(Item=_to_item(challenge))
        return challenge

    def consume(
        self,
        challenge_id: str,
        *,
        consumed_at: str,
        expected_attempt_count: int,
    ) -> StoredStaffPasswordResetChallenge | None:
        """Conditional consume — only one concurrent confirm can win."""
        try:
            response = self._table.update_item(
                Key={"challengeId": challenge_id},
                UpdateExpression="SET consumedAt = :at ADD attemptCount :one",
                ConditionExpression=(f"{_LIVE_CHALLENGE_CONDITION} AND attemptCount = :expected"),
                ExpressionAttributeValues={
                    ":at": consumed_at,
                    ":one": 1,
                    ":expected": expected_attempt_count,
                },
                ReturnValues="ALL_NEW",
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise
        return _from_item(response["Attributes"])

    def increment_attempt(self, challenge_id: str) -> StoredStaffPasswordResetChallenge | None:
        """Conditional attempt bump — loses cleanly if already consumed."""
        try:
            response = self._table.update_item(
                Key={"challengeId": challenge_id},
                UpdateExpression="ADD attemptCount :one",
                ConditionExpression=_LIVE_CHALLENGE_CONDITION,
                ExpressionAttributeValues={":one": 1},
                ReturnValues="ALL_NEW",
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise
        return _from_item(response["Attributes"])

    def clear(self) -> None:
        raise NotImplementedError(
            "DynamoStaffPasswordResetStore does not support clear(). Use db-reset."
        )
