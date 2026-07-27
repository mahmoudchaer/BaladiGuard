from decimal import Decimal

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import item_to_ticket, prepare_dynamodb_value, ticket_to_item
from app.database.ticket_patch import build_update_expression
from app.schemas.stored_ticket import StoredTicket
from app.schemas.ticket_response import TicketStatus

TICKET_NUMBER_COUNTER_ID = "ticketNumberSequence"


class DynamoTicketStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._resource = create_dynamodb_resource(self._settings)
        prefix = self._settings.dynamodb_table_prefix
        self._tickets_table = self._resource.Table(build_table_name(prefix, "tickets"))
        self._counters_table = self._resource.Table(build_table_name(prefix, "counters"))

    def next_sequence(self) -> int:
        response = self._counters_table.update_item(
            Key={"counterId": TICKET_NUMBER_COUNTER_ID},
            UpdateExpression="SET #value = if_not_exists(#value, :start) + :increment",
            ExpressionAttributeNames={"#value": "value"},
            ExpressionAttributeValues={
                ":start": Decimal(0),
                ":increment": Decimal(1),
            },
            ReturnValues="UPDATED_NEW",
        )
        return int(response["Attributes"]["value"])

    def save(self, ticket: StoredTicket) -> None:
        self._tickets_table.put_item(Item=ticket_to_item(ticket))

    def get(self, ticket_id: str) -> StoredTicket | None:
        response = self._tickets_table.get_item(Key={"ticketId": ticket_id})
        item = response.get("Item")
        if not item:
            return None
        return item_to_ticket(item)

    def get_by_tracking_code(self, tracking_code: str) -> StoredTicket | None:
        response = self._tickets_table.query(
            IndexName="trackingCode-index",
            KeyConditionExpression=Key("trackingCode").eq(tracking_code.strip().upper()),
            Limit=1,
        )
        items = response.get("Items", [])
        if not items:
            return None
        return item_to_ticket(items[0])

    def list(self) -> list[StoredTicket]:
        tickets: list[StoredTicket] = []
        scan_kwargs: dict[str, object] = {}

        while True:
            response = self._tickets_table.scan(**scan_kwargs)
            tickets.extend(item_to_ticket(item) for item in response.get("Items", []))

            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key

        return tickets

    def patch_fields(
        self,
        ticket_id: str,
        fields: dict[str, object],
    ) -> StoredTicket | None:
        """Apply a partial attribute update so concurrent writers do not clobber each other."""
        expression, names, values = build_update_expression(fields)
        update_kwargs: dict[str, object] = {
            "Key": {"ticketId": ticket_id},
            "UpdateExpression": expression,
            "ConditionExpression": "attribute_exists(ticketId)",
            "ExpressionAttributeNames": names,
            "ReturnValues": "ALL_NEW",
        }
        if values:
            update_kwargs["ExpressionAttributeValues"] = prepare_dynamodb_value(values)
        try:
            response = self._tickets_table.update_item(**update_kwargs)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise

        return item_to_ticket(response["Attributes"])

    def update_status(
        self,
        ticket_id: str,
        status: TicketStatus,
        updated_at: str,
    ) -> StoredTicket | None:
        try:
            response = self._tickets_table.update_item(
                Key={"ticketId": ticket_id},
                UpdateExpression="SET #status = :status, #updatedAt = :updatedAt",
                ConditionExpression="attribute_exists(ticketId)",
                ExpressionAttributeNames={
                    "#status": "status",
                    "#updatedAt": "updatedAt",
                },
                ExpressionAttributeValues={
                    ":status": status,
                    ":updatedAt": updated_at,
                },
                ReturnValues="ALL_NEW",
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise

        return item_to_ticket(response["Attributes"])

    def claim_ai_processing(
        self,
        ticket_id: str,
        updated_at: str,
    ) -> StoredTicket | None:
        """Atomically claim a pending ticket for AI work (pending → processing)."""
        try:
            response = self._tickets_table.update_item(
                Key={"ticketId": ticket_id},
                UpdateExpression=("SET #aiProcessingStatus = :processing, #updatedAt = :updatedAt"),
                ConditionExpression="#aiProcessingStatus = :pending",
                ExpressionAttributeNames={
                    "#aiProcessingStatus": "aiProcessingStatus",
                    "#updatedAt": "updatedAt",
                },
                ExpressionAttributeValues={
                    ":pending": "pending",
                    ":processing": "processing",
                    ":updatedAt": updated_at,
                },
                ReturnValues="ALL_NEW",
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise

        return item_to_ticket(response["Attributes"])

    def release_ai_processing_claim(
        self,
        ticket_id: str,
        updated_at: str,
    ) -> StoredTicket | None:
        """Return a stuck processing claim to pending so recovery can reclaim it."""
        try:
            response = self._tickets_table.update_item(
                Key={"ticketId": ticket_id},
                UpdateExpression=("SET #aiProcessingStatus = :pending, #updatedAt = :updatedAt"),
                ConditionExpression="#aiProcessingStatus = :processing",
                ExpressionAttributeNames={
                    "#aiProcessingStatus": "aiProcessingStatus",
                    "#updatedAt": "updatedAt",
                },
                ExpressionAttributeValues={
                    ":pending": "pending",
                    ":processing": "processing",
                    ":updatedAt": updated_at,
                },
                ReturnValues="ALL_NEW",
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise

        return item_to_ticket(response["Attributes"])

    def has_ticket_id(self, ticket_id: str) -> bool:
        response = self._tickets_table.get_item(
            Key={"ticketId": ticket_id},
            ProjectionExpression="ticketId",
        )
        return "Item" in response

    def has_ticket_number(self, ticket_number: str) -> bool:
        response = self._tickets_table.query(
            IndexName="ticketNumber-index",
            KeyConditionExpression=Key("ticketNumber").eq(ticket_number),
            Limit=1,
            ProjectionExpression="ticketId",
        )
        return bool(response.get("Items"))

    def has_tracking_code(self, tracking_code: str) -> bool:
        response = self._tickets_table.query(
            IndexName="trackingCode-index",
            KeyConditionExpression=Key("trackingCode").eq(tracking_code),
            Limit=1,
            ProjectionExpression="ticketId",
        )
        return bool(response.get("Items"))

    def clear(self) -> None:
        message = "DynamoTicketStore does not support clear(). Use db-reset for local dev."
        raise NotImplementedError(message)
