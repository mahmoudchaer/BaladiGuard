"""DynamoDB citizen account store with transactional phone claims (issue #169)."""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.citizen_store import (
    CitizenNotFoundError,
    CitizenPhoneMismatchError,
    PhoneClaimConflictError,
)
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import convert_decimals, prepare_dynamodb_value
from app.schemas.citizen import StoredCitizenUser
from app.utils.phone import phone_claim_key

_SERIALIZER = TypeSerializer()


def _user_to_item(user: StoredCitizenUser) -> dict[str, Any]:
    item = user.model_dump(by_alias=True, mode="json")
    filtered = {key: value for key, value in item.items() if value is not None}
    return prepare_dynamodb_value(filtered)


def _item_to_user(item: dict[str, Any]) -> StoredCitizenUser:
    return StoredCitizenUser.model_validate(convert_decimals(item))


def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: _SERIALIZER.serialize(value) for key, value in item.items()}


def _serialize_values(values: dict[str, Any]) -> dict[str, Any]:
    return {key: _SERIALIZER.serialize(value) for key, value in values.items()}


def _to_wire_transact_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert document-form TransactItems to low-level AttributeValue form."""
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


class DynamoCitizenStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._resource = create_dynamodb_resource(self._settings)
        prefix = self._settings.dynamodb_table_prefix
        self._users_table = self._resource.Table(build_table_name(prefix, "users"))
        self._claims_table = self._resource.Table(build_table_name(prefix, "phone-claims"))
        self._client = self._resource.meta.client

    def _transact_write(self, items: list[dict[str, Any]]) -> None:
        """Run TransactWriteItems.

        Real DynamoDB requires AttributeValue wire format. moto's
        TransactWriteItems currently mishandles pre-serialized items and expects
        native document types, so fall back when that specific failure appears.
        """
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

    def create(self, user: StoredCitizenUser) -> StoredCitizenUser:
        claim_key = phone_claim_key(user.phone)
        try:
            self._transact_write(
                [
                    {
                        "Put": {
                            "TableName": self._claims_table.name,
                            "Item": {
                                "phoneKey": claim_key,
                                "userId": user.user_id,
                                "createdAt": user.created_at,
                            },
                            "ConditionExpression": "attribute_not_exists(phoneKey)",
                        }
                    },
                    {
                        "Put": {
                            "TableName": self._users_table.name,
                            "Item": _user_to_item(user),
                            "ConditionExpression": "attribute_not_exists(userId)",
                        }
                    },
                ]
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "TransactionCanceledException":
                raise PhoneClaimConflictError("Phone number is already claimed.") from error
            raise
        return user

    def get(self, user_id: str) -> StoredCitizenUser | None:
        # Strongly consistent: auth checks sessionEpoch immediately after phone
        # change / revocation and must not observe a stale generation.
        response = self._users_table.get_item(
            Key={"userId": user_id},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not item:
            return None
        return _item_to_user(item)

    def get_by_phone(self, canonical_phone: str) -> StoredCitizenUser | None:
        claim_key = phone_claim_key(canonical_phone)
        claim_response = self._claims_table.get_item(
            Key={"phoneKey": claim_key},
            ConsistentRead=True,
        )
        claim = claim_response.get("Item")
        if not claim:
            return None
        user_id = claim.get("userId")
        if not isinstance(user_id, str):
            return None
        return self.get(user_id)

    def update(self, user: StoredCitizenUser) -> StoredCitizenUser:
        existing = self.get(user.user_id)
        if existing is None:
            raise CitizenNotFoundError("Citizen not found.")
        if existing.phone != user.phone:
            raise CitizenPhoneMismatchError("Phone changes must use change_phone(), not update().")
        try:
            self._users_table.put_item(
                Item=_user_to_item(user),
                ConditionExpression="attribute_exists(userId) AND phone = :phone",
                ExpressionAttributeValues={":phone": existing.phone},
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                raise CitizenPhoneMismatchError("Current phone no longer matches.") from error
            raise
        return user

    def change_phone(
        self,
        *,
        user_id: str,
        old_phone: str,
        updated_user: StoredCitizenUser,
    ) -> StoredCitizenUser:
        if updated_user.user_id != user_id:
            raise CitizenPhoneMismatchError("Updated userId does not match.")
        old_key = phone_claim_key(old_phone)
        new_key = phone_claim_key(updated_user.phone)
        existing = self.get(user_id)
        if existing is None:
            raise CitizenNotFoundError("Citizen not found.")
        if existing.phone != old_phone:
            raise CitizenPhoneMismatchError("Current phone no longer matches.")

        transact_items: list[dict[str, Any]] = [
            {
                "Put": {
                    "TableName": self._claims_table.name,
                    "Item": {
                        "phoneKey": new_key,
                        "userId": user_id,
                        "createdAt": updated_user.phone_verified_at,
                    },
                    "ConditionExpression": "attribute_not_exists(phoneKey)",
                }
            },
            {
                "Put": {
                    "TableName": self._users_table.name,
                    "Item": _user_to_item(updated_user),
                    "ConditionExpression": "attribute_exists(userId) AND phone = :oldPhone",
                    "ExpressionAttributeValues": {":oldPhone": old_phone},
                }
            },
        ]
        if old_key != new_key:
            transact_items.append(
                {
                    "Delete": {
                        "TableName": self._claims_table.name,
                        "Key": {"phoneKey": old_key},
                        "ConditionExpression": "userId = :userId",
                        "ExpressionAttributeValues": {":userId": user_id},
                    }
                }
            )

        try:
            self._transact_write(transact_items)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code == "TransactionCanceledException":
                reasons = error.response.get("CancellationReasons") or []
                if reasons and reasons[0].get("Code") == "ConditionalCheckFailed":
                    raise PhoneClaimConflictError("Phone number is already claimed.") from error
                raise CitizenPhoneMismatchError("Unable to transfer phone claim.") from error
            raise
        return updated_user

    def clear(self) -> None:
        message = "DynamoCitizenStore does not support clear(). Use db-reset for local dev."
        raise NotImplementedError(message)
