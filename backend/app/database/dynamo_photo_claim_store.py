from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name


class DynamoPhotoClaimStore:
    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        resource = create_dynamodb_resource(settings)
        self._table = resource.Table(
            build_table_name(settings.dynamodb_table_prefix, "photo-upload-claims")
        )

    def claim(self, object_key: str, *, owner_scope: str, ticket_id: str) -> bool:
        try:
            self._table.put_item(
                Item={
                    "objectKey": object_key,
                    "ownerScope": owner_scope,
                    "ticketId": ticket_id,
                },
                ConditionExpression="attribute_not_exists(objectKey)",
            )
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise

    def release(self, object_key: str, *, ticket_id: str) -> bool:
        try:
            self._table.delete_item(
                Key={"objectKey": object_key},
                ConditionExpression="ticketId = :ticketId",
                ExpressionAttributeValues={":ticketId": ticket_id},
            )
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise

    def clear(self) -> None:
        raise NotImplementedError("Use db-reset for DynamoDB-backed photo claims.")
