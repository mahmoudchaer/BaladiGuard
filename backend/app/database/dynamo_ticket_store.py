from decimal import Decimal

from boto3.dynamodb.conditions import Key

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import item_to_ticket, ticket_to_item
from app.schemas.stored_ticket import StoredTicket

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
