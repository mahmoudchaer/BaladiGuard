"""DynamoDB citizen OTP challenge store (issue #169 phone-change foundation)."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import convert_decimals, prepare_dynamodb_value
from app.schemas.citizen_session import StoredCitizenOtpChallenge


def _to_item(challenge: StoredCitizenOtpChallenge) -> dict[str, Any]:
    item = challenge.model_dump(by_alias=True, mode="json")
    filtered = {key: value for key, value in item.items() if value is not None}
    return prepare_dynamodb_value(filtered)


def _from_item(item: dict[str, Any]) -> StoredCitizenOtpChallenge:
    return StoredCitizenOtpChallenge.model_validate(convert_decimals(item))


class DynamoCitizenOtpStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._resource = create_dynamodb_resource(self._settings)
        prefix = self._settings.dynamodb_table_prefix
        self._table = self._resource.Table(build_table_name(prefix, "citizen-otp-challenges"))

    def create(self, challenge: StoredCitizenOtpChallenge) -> StoredCitizenOtpChallenge:
        # Best-effort supersede of prior live challenges for the same phone/purpose/user.
        # Exact uniqueness is enforced at consume time by conditional updates.
        scan_filter = {
            ":phone": challenge.phone,
            ":purpose": challenge.purpose,
        }
        filter_expression = (
            "phone = :phone AND purpose = :purpose "
            "AND attribute_not_exists(consumedAt) "
            "AND attribute_not_exists(supersededAt)"
        )
        if challenge.user_id is not None:
            filter_expression += " AND userId = :userId"
            scan_filter[":userId"] = challenge.user_id
        else:
            filter_expression += " AND attribute_not_exists(userId)"

        scan_kwargs: dict[str, object] = {
            "FilterExpression": filter_expression,
            "ExpressionAttributeValues": scan_filter,
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

    def get(self, challenge_id: str) -> StoredCitizenOtpChallenge | None:
        response = self._table.get_item(Key={"challengeId": challenge_id})
        item = response.get("Item")
        if not item:
            return None
        return _from_item(item)

    def save(self, challenge: StoredCitizenOtpChallenge) -> StoredCitizenOtpChallenge:
        self._table.put_item(Item=_to_item(challenge))
        return challenge

    def clear(self) -> None:
        raise NotImplementedError(
            "DynamoCitizenOtpStore does not support clear(). Use db-reset for local dev."
        )
