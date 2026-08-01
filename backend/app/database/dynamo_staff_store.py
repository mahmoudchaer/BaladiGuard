"""DynamoDB staff account store with transactional username claims (issue #175)."""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import convert_decimals, prepare_dynamodb_value
from app.database.staff_store import StaffNotFoundError, StaffUsernameConflictError
from app.schemas.staff_user import StoredStaffUser, staff_username_claim_key

_SERIALIZER = TypeSerializer()


def _user_to_item(user: StoredStaffUser) -> dict[str, Any]:
    item = user.model_dump(by_alias=True, mode="json")
    # Omit nulls; administrator scope sentinels are reconstructed as None on read.
    filtered = {key: value for key, value in item.items() if value is not None}
    return prepare_dynamodb_value(filtered)


def _item_to_user(item: dict[str, Any]) -> StoredStaffUser:
    return StoredStaffUser.model_validate(convert_decimals(item))


def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: _SERIALIZER.serialize(value) for key, value in item.items()}


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
            converted["ExpressionAttributeValues"] = {
                key: _SERIALIZER.serialize(value)
                for key, value in converted["ExpressionAttributeValues"].items()
            }
        wired.append({action: converted})
    return wired


class DynamoStaffStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._resource = create_dynamodb_resource(self._settings)
        prefix = self._settings.dynamodb_table_prefix
        self._users_table = self._resource.Table(build_table_name(prefix, "staff-users"))
        self._claims_table = self._resource.Table(build_table_name(prefix, "staff-username-claims"))
        self._client = self._resource.meta.client

    def _transact_write(self, items: list[dict[str, Any]]) -> None:
        try:
            self._client.transact_write_items(TransactItems=_to_wire_transact_items(items))
            return
        except ClientError as error:
            reasons = error.response.get("CancellationReasons") or []
            moto_type_error = any(
                reason.get("Code") == "TypeError" or "unhashable" in str(reason.get("Message", ""))
                for reason in reasons
            )
            if not moto_type_error:
                raise
        self._client.transact_write_items(TransactItems=items)

    def create(self, user: StoredStaffUser) -> StoredStaffUser:
        claim_key = staff_username_claim_key(user.username)
        try:
            self._transact_write(
                [
                    {
                        "Put": {
                            "TableName": self._claims_table.name,
                            "Item": {
                                "usernameKey": claim_key,
                                "staffId": user.staff_id,
                                "createdAt": user.created_at,
                            },
                            "ConditionExpression": "attribute_not_exists(usernameKey)",
                        }
                    },
                    {
                        "Put": {
                            "TableName": self._users_table.name,
                            "Item": _user_to_item(user),
                            "ConditionExpression": "attribute_not_exists(staffId)",
                        }
                    },
                ]
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "TransactionCanceledException":
                raise StaffUsernameConflictError("Username is already claimed.") from error
            raise
        return user

    def get(self, staff_id: str) -> StoredStaffUser | None:
        response = self._users_table.get_item(
            Key={"staffId": staff_id},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not item:
            return None
        return _item_to_user(item)

    def get_by_username(self, username: str) -> StoredStaffUser | None:
        claim_key = staff_username_claim_key(username)
        claim_response = self._claims_table.get_item(
            Key={"usernameKey": claim_key},
            ConsistentRead=True,
        )
        claim = claim_response.get("Item")
        if not claim:
            return None
        staff_id = claim.get("staffId")
        if not isinstance(staff_id, str):
            return None
        return self.get(staff_id)

    def update(self, user: StoredStaffUser) -> StoredStaffUser:
        existing = self.get(user.staff_id)
        if existing is None:
            raise StaffNotFoundError("Staff account not found.")
        if existing.username != user.username:
            raise StaffUsernameConflictError("Username changes are not supported.")
        try:
            self._users_table.put_item(
                Item=_user_to_item(user),
                ConditionExpression="attribute_exists(staffId) AND username = :username",
                ExpressionAttributeValues={":username": existing.username},
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                raise StaffNotFoundError("Staff account not found.") from error
            raise
        return user

    def clear(self) -> None:
        raise NotImplementedError(
            "DynamoStaffStore does not support clear(). Use db-reset for local dev."
        )
