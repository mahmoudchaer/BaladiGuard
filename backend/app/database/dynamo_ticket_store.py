import base64
import binascii
import json
from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import (
    OWNER_HISTORY_SORT_KEY,
    PUBLIC_INDEX_FIELDS,
    PUBLIC_SORT_KEY,
    PUBLIC_TICKET_STATUS_PUBLISHED,
    build_public_sort_key,
    is_public_ticket_publishable,
    item_to_ticket,
    prepare_dynamodb_value,
    ticket_to_item,
)
from app.database.ticket_patch import build_update_expression
from app.database.ticket_store import TicketHistoryPage
from app.schemas.stored_ticket import StoredTicket
from app.schemas.ticket_response import TicketStatus
from app.utils.ticket_ids import normalize_tracking_code

TICKET_NUMBER_COUNTER_ID = "ticketNumberSequence"
OWNER_HISTORY_INDEX = "ownerUserId-ownerHistorySortKey-index"
PUBLIC_TICKETS_INDEX = "publicStatus-publicSortKey-index"


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
            KeyConditionExpression=Key("trackingCode").eq(normalize_tracking_code(tracking_code)),
            Limit=1,
        )
        items = response.get("Items", [])
        if not items:
            return None
        return item_to_ticket(items[0])

    def get_by_ticket_number(self, ticket_number: str) -> StoredTicket | None:
        response = self._tickets_table.query(
            IndexName="ticketNumber-index",
            KeyConditionExpression=Key("ticketNumber").eq(ticket_number.strip().upper()),
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

    def list_by_owner(
        self,
        owner_user_id: str,
        *,
        limit: int,
        cursor: str | None = None,
    ) -> TicketHistoryPage:
        query_kwargs: dict[str, object] = {
            "IndexName": OWNER_HISTORY_INDEX,
            "KeyConditionExpression": Key("ownerUserId").eq(owner_user_id),
            "ScanIndexForward": False,
            "Limit": limit,
        }
        if cursor:
            query_kwargs["ExclusiveStartKey"] = _decode_owner_history_cursor(
                cursor,
                owner_user_id=owner_user_id,
            )

        response = self._tickets_table.query(**query_kwargs)
        return TicketHistoryPage(
            [item_to_ticket(item) for item in response.get("Items", [])],
            _encode_owner_history_cursor(response.get("LastEvaluatedKey")),
        )

    def list_public(
        self,
        *,
        limit: int,
        cursor: str | None = None,
    ) -> TicketHistoryPage:
        query_kwargs: dict[str, object] = {
            "IndexName": PUBLIC_TICKETS_INDEX,
            "KeyConditionExpression": Key("publicStatus").eq(PUBLIC_TICKET_STATUS_PUBLISHED),
            "ScanIndexForward": False,
            "Limit": limit,
        }
        if cursor:
            query_kwargs["ExclusiveStartKey"] = _decode_public_cursor(cursor)

        items: list[dict[str, Any]] = []
        last_key: dict[str, Any] | None = None
        while len(items) < limit:
            response = self._tickets_table.query(**query_kwargs)
            last_key = response.get("LastEvaluatedKey")
            for item in response.get("Items", []):
                ticket = item_to_ticket(item)
                if is_public_ticket_publishable(ticket):
                    items.append(item)
                    if len(items) == limit:
                        break
            if not last_key or len(items) == limit:
                break
            query_kwargs["ExclusiveStartKey"] = last_key

        return TicketHistoryPage(
            [item_to_ticket(item) for item in items],
            _encode_public_cursor(last_key),
        )

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

        updated_ticket = item_to_ticket(response["Attributes"])
        if PUBLIC_INDEX_FIELDS.intersection(fields):
            self._sync_public_index_fields(updated_ticket)
        return updated_ticket

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
        claim_token: str | None = None,
    ) -> StoredTicket | None:
        """Atomically claim a pending ticket for AI work (pending → processing)."""
        try:
            response = self._tickets_table.update_item(
                Key={"ticketId": ticket_id},
                UpdateExpression=(
                    "SET #aiProcessingStatus = :processing, #updatedAt = :updatedAt, "
                    "aiProcessingClaimToken = :claimToken"
                ),
                ConditionExpression="#aiProcessingStatus = :pending",
                ExpressionAttributeNames={
                    "#aiProcessingStatus": "aiProcessingStatus",
                    "#updatedAt": "updatedAt",
                },
                ExpressionAttributeValues={
                    ":pending": "pending",
                    ":processing": "processing",
                    ":updatedAt": updated_at,
                    ":claimToken": claim_token or "",
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
                UpdateExpression=(
                    "SET #aiProcessingStatus = :pending, #updatedAt = :updatedAt "
                    "REMOVE aiProcessingClaimToken"
                ),
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

    def requeue_ai_processing(self, ticket_id: str, updated_at: str) -> StoredTicket | None:
        """Reset failed/stale processing unless a completed result already exists."""
        try:
            response = self._tickets_table.update_item(
                Key={"ticketId": ticket_id},
                UpdateExpression=(
                    "SET #ai = :pending, #updatedAt = :updatedAt REMOVE aiProcessingClaimToken"
                ),
                ConditionExpression="attribute_exists(ticketId) AND #ai <> :completed",
                ExpressionAttributeNames={
                    "#ai": "aiProcessingStatus",
                    "#updatedAt": "updatedAt",
                },
                ExpressionAttributeValues={
                    ":pending": "pending",
                    ":completed": "completed",
                    ":updatedAt": updated_at,
                },
                ReturnValues="ALL_NEW",
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise
        return item_to_ticket(response["Attributes"])

    def patch_ai_fields(
        self, ticket_id: str, claim_token: str, fields: dict[str, object]
    ) -> StoredTicket | None:
        expression, names, values = build_update_expression(
            {**fields, "ai_processing_claim_token": None}
        )
        names["#ai"] = "aiProcessingStatus"
        values[":processing"] = "processing"
        values[":claimToken"] = claim_token
        try:
            response = self._tickets_table.update_item(
                Key={"ticketId": ticket_id},
                UpdateExpression=expression,
                ConditionExpression=("#ai = :processing AND aiProcessingClaimToken = :claimToken"),
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
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
            KeyConditionExpression=Key("trackingCode").eq(normalize_tracking_code(tracking_code)),
            Limit=1,
            ProjectionExpression="ticketId",
        )
        return bool(response.get("Items"))

    def clear(self) -> None:
        message = "DynamoTicketStore does not support clear(). Use db-reset for local dev."
        raise NotImplementedError(message)

    def _sync_public_index_fields(self, ticket: StoredTicket) -> None:
        if is_public_ticket_publishable(ticket):
            self._tickets_table.update_item(
                Key={"ticketId": ticket.ticket_id},
                UpdateExpression="SET #publicSortKey = :publicSortKey",
                ExpressionAttributeNames={"#publicSortKey": PUBLIC_SORT_KEY},
                ExpressionAttributeValues={":publicSortKey": build_public_sort_key(ticket)},
            )
            return
        self._tickets_table.update_item(
            Key={"ticketId": ticket.ticket_id},
            UpdateExpression="REMOVE #publicSortKey",
            ExpressionAttributeNames={"#publicSortKey": PUBLIC_SORT_KEY},
        )


def _encode_owner_history_cursor(last_key: dict[str, Any] | None) -> str | None:
    if not last_key:
        return None
    payload = {
        "ownerUserId": last_key.get("ownerUserId"),
        "ownerHistorySortKey": last_key.get(OWNER_HISTORY_SORT_KEY),
        "ticketId": last_key.get("ticketId"),
    }
    if not all(isinstance(value, str) for value in payload.values()):
        raise ValueError("Invalid owner history cursor.")
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_owner_history_cursor(
    cursor: str,
    *,
    owner_user_id: str,
) -> dict[str, str]:
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid owner history cursor.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid owner history cursor.")
    decoded_owner = payload.get("ownerUserId")
    sort_key = payload.get("ownerHistorySortKey")
    ticket_id = payload.get("ticketId")
    if (
        decoded_owner != owner_user_id
        or not isinstance(sort_key, str)
        or not isinstance(ticket_id, str)
    ):
        raise ValueError("Invalid owner history cursor.")
    return {
        "ownerUserId": decoded_owner,
        OWNER_HISTORY_SORT_KEY: sort_key,
        "ticketId": ticket_id,
    }


def _encode_public_cursor(last_key: dict[str, Any] | None) -> str | None:
    if not last_key:
        return None
    payload = {
        "publicStatus": last_key.get("publicStatus"),
        "publicSortKey": last_key.get(PUBLIC_SORT_KEY),
        "ticketId": last_key.get("ticketId"),
    }
    if not all(isinstance(value, str) for value in payload.values()):
        raise ValueError("Invalid public ticket cursor.")
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_public_cursor(cursor: str) -> dict[str, str]:
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid public ticket cursor.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid public ticket cursor.")
    public_status = payload.get("publicStatus")
    sort_key = payload.get("publicSortKey")
    ticket_id = payload.get("ticketId")
    if (
        public_status != PUBLIC_TICKET_STATUS_PUBLISHED
        or not isinstance(sort_key, str)
        or not isinstance(ticket_id, str)
    ):
        raise ValueError("Invalid public ticket cursor.")
    return {
        "publicStatus": public_status,
        PUBLIC_SORT_KEY: sort_key,
        "ticketId": ticket_id,
    }
