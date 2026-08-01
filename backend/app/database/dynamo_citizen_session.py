"""DynamoDB citizen session store (issue #169)."""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import convert_decimals, prepare_dynamodb_value
from app.schemas.citizen_session import StoredCitizenSession


def _to_item(session: StoredCitizenSession) -> dict[str, Any]:
    item = session.model_dump(by_alias=True, mode="json")
    filtered = {key: value for key, value in item.items() if value is not None}
    return prepare_dynamodb_value(filtered)


def _from_item(item: dict[str, Any]) -> StoredCitizenSession:
    return StoredCitizenSession.model_validate(convert_decimals(item))


class DynamoCitizenSessionStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._resource = create_dynamodb_resource(self._settings)
        prefix = self._settings.dynamodb_table_prefix
        self._table = self._resource.Table(build_table_name(prefix, "citizen-sessions"))

    def create(self, session: StoredCitizenSession) -> StoredCitizenSession:
        self._table.put_item(Item=_to_item(session))
        return session

    def get(self, session_id: str) -> StoredCitizenSession | None:
        response = self._table.get_item(Key={"sessionId": session_id})
        item = response.get("Item")
        if not item:
            return None
        return _from_item(item)

    def revoke(
        self,
        session_id: str,
        *,
        revoked_at: str,
        reason: str,
    ) -> StoredCitizenSession | None:
        try:
            response = self._table.update_item(
                Key={"sessionId": session_id},
                UpdateExpression="SET revokedAt = :revokedAt, revokeReason = :reason",
                ConditionExpression=(
                    "attribute_exists(sessionId) AND attribute_not_exists(revokedAt)"
                ),
                ExpressionAttributeValues={
                    ":revokedAt": revoked_at,
                    ":reason": reason,
                },
                ReturnValues="ALL_NEW",
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return self.get(session_id)
            raise
        return _from_item(response["Attributes"])

    def revoke_all_for_user(
        self,
        user_id: str,
        *,
        revoked_at: str,
        reason: str,
    ) -> int:
        count = 0
        query_kwargs: dict[str, object] = {
            "IndexName": "userId-index",
            "KeyConditionExpression": Key("userId").eq(user_id),
        }
        while True:
            response = self._table.query(**query_kwargs)
            for item in response.get("Items", []):
                session = _from_item(item)
                if session.revoked_at is not None:
                    continue
                if self.revoke(session.session_id, revoked_at=revoked_at, reason=reason):
                    count += 1
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key
        return count

    def clear(self) -> None:
        raise NotImplementedError(
            "DynamoCitizenSessionStore does not support clear(). Use db-reset for local dev."
        )
