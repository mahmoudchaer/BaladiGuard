from __future__ import annotations

import base64
import binascii
import json
from decimal import Decimal
from typing import Any, Literal

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import (
    ADMIN_BROWSE_ALL,
    ADMIN_BROWSE_KEY,
    OWNER_HISTORY_SORT_KEY,
    PUBLIC_INDEX_FIELDS,
    PUBLIC_SORT_KEY,
    PUBLIC_TICKET_STATUS_PUBLISHED,
    STAFF_SCOPE_KEY,
    STAFF_SORT_KEY,
    build_public_sort_key,
    is_public_ticket_publishable,
    item_to_ticket,
    prepare_dynamodb_value,
    ticket_to_item,
)
from app.database.ticket_patch import (
    append_redaction_review_condition,
    append_ticket_access_scope_condition,
    append_ticket_assignment_scope_condition,
    build_update_expression,
)
from app.database.ticket_store import (
    StaffTicketPage,
    TicketHistoryPage,
    public_ticket_matches_query,
)
from app.schemas.stored_ticket import StoredTicket
from app.schemas.ticket_response import TicketStatus
from app.utils.ticket_ids import normalize_tracking_code

TICKET_NUMBER_COUNTER_ID = "ticketNumberSequence"
OWNER_HISTORY_INDEX = "ownerUserId-ownerHistorySortKey-index"
PUBLIC_TICKETS_INDEX = "publicStatus-publicSortKey-index"
STAFF_SCOPE_INDEX = "staffScopeKey-staffSortKey-index"
ADMIN_BROWSE_INDEX = "adminBrowseKey-staffSortKey-index"
DEPARTMENT_STAFF_INDEX = "departmentId-staffSortKey-index"
STAFF_QUERY_MAX_ROUNDS = 5


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
        response = self._tickets_table.get_item(
            Key={"ticketId": ticket_id},
            ConsistentRead=True,
        )
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

    def list_staff_page(
        self,
        *,
        browse_mode: Literal["admin", "municipality"],
        municipality_id: str | None,
        department_ids: list[str] | None,
        limit: int,
        cursor: str | None,
        status: str | None = None,
        category: str | None = None,
        urgency: str | None = None,
        department_id: str | None = None,
        assignment_state: Literal["assigned", "unassigned"] | None = None,
        q: str | None = None,
        open_only: bool = False,
    ) -> StaffTicketPage:
        """Indexed staff collection page.

        ``sla_state`` is intentionally omitted: callers apply it in the service
        layer after fetch (Dynamo cannot derive SLA from stored attributes alone).
        Unsupported combinations must not fall back to an unbounded table scan.
        """
        index_name, hash_name, hash_value = _staff_query_target(
            browse_mode=browse_mode,
            municipality_id=municipality_id,
            department_id=department_id,
        )
        filter_expression = _staff_filter_expression(
            status=status,
            category=category,
            urgency=urgency,
            department_id=department_id if index_name != DEPARTMENT_STAFF_INDEX else None,
            department_ids=(
                department_ids if browse_mode == "municipality" and department_id is None else None
            ),
            assignment_state=assignment_state,
            q=q,
            open_only=open_only,
        )

        query_kwargs: dict[str, object] = {
            "IndexName": index_name,
            "KeyConditionExpression": Key(hash_name).eq(hash_value),
            "ScanIndexForward": False,
            "Limit": limit,
        }
        if filter_expression is not None:
            query_kwargs["FilterExpression"] = filter_expression
        if cursor:
            query_kwargs["ExclusiveStartKey"] = _decode_staff_cursor(
                cursor,
                index_name=index_name,
                hash_name=hash_name,
                hash_value=hash_value,
            )

        items: list[StoredTicket] = []
        scanned_count = 0
        last_key: dict[str, Any] | None = None
        for _ in range(STAFF_QUERY_MAX_ROUNDS):
            response = self._tickets_table.query(**query_kwargs)
            scanned_count += int(response.get("ScannedCount") or len(response.get("Items", [])))
            last_key = response.get("LastEvaluatedKey")
            for item in response.get("Items", []):
                ticket = item_to_ticket(item)
                if browse_mode == "municipality" and not _municipal_post_filter(
                    ticket,
                    municipality_id=municipality_id,
                    department_ids=department_ids,
                    department_id=department_id,
                ):
                    continue
                items.append(ticket)
                if len(items) == limit:
                    break
            if not last_key or len(items) == limit:
                break
            query_kwargs["ExclusiveStartKey"] = last_key

        next_cursor = None
        if last_key:
            # Always continue when Dynamo still has unread keys — sparse
            # FilterExpression pages can end a bounded round with items < limit
            # while later matches remain (issue #267 review).
            next_cursor = _encode_staff_cursor(last_key, index_name=index_name)
        elif len(items) == limit and items:
            # Cap reached mid-page without Dynamo LEK; synthesize from last item.
            next_cursor = _encode_staff_cursor(
                _synthetic_staff_start_key(
                    items[-1],
                    index_name=index_name,
                    hash_name=hash_name,
                    hash_value=hash_value,
                ),
                index_name=index_name,
            )

        return StaffTicketPage(items, next_cursor, scanned_count)

    def staff_continuation_cursor(
        self,
        ticket: StoredTicket,
        *,
        browse_mode: Literal["admin", "municipality"],
        municipality_id: str | None,
        department_id: str | None = None,
    ) -> str:
        index_name, hash_name, hash_value = _staff_query_target(
            browse_mode=browse_mode,
            municipality_id=municipality_id,
            department_id=department_id,
        )
        encoded = _encode_staff_cursor(
            _synthetic_staff_start_key(
                ticket,
                index_name=index_name,
                hash_name=hash_name,
                hash_value=hash_value,
            ),
            index_name=index_name,
        )
        if encoded is None:
            raise ValueError("Unable to encode staff continuation cursor.")
        return encoded

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
        q: str | None = None,
        status: TicketStatus | None = None,
        category: str | None = None,
        north: float | None = None,
        south: float | None = None,
        east: float | None = None,
        west: float | None = None,
    ) -> TicketHistoryPage:
        query_kwargs: dict[str, object] = {
            "IndexName": PUBLIC_TICKETS_INDEX,
            "KeyConditionExpression": Key("publicStatus").eq(PUBLIC_TICKET_STATUS_PUBLISHED),
            "ScanIndexForward": False,
            "Limit": limit,
        }
        if cursor:
            query_kwargs["ExclusiveStartKey"] = _decode_public_cursor(cursor)

        tickets: list[StoredTicket] = []
        last_key: dict[str, Any] | None = None
        while len(tickets) <= limit:
            response = self._tickets_table.query(**query_kwargs)
            last_key = response.get("LastEvaluatedKey")
            for item in response.get("Items", []):
                ticket = item_to_ticket(item)
                if is_public_ticket_publishable(ticket) and public_ticket_matches_query(
                    ticket,
                    q=q,
                    status=status,
                    category=category,
                    north=north,
                    south=south,
                    east=east,
                    west=west,
                ):
                    tickets.append(ticket)
                    if len(tickets) > limit:
                        break
            if not last_key or len(tickets) > limit:
                break
            query_kwargs["ExclusiveStartKey"] = last_key

        page = tickets[:limit]
        next_cursor = self.public_continuation_cursor(page[-1]) if len(tickets) > limit else None
        return TicketHistoryPage(
            page,
            next_cursor,
        )

    def public_continuation_cursor(self, ticket: StoredTicket) -> str:
        cursor = _encode_public_cursor(
            {
                "publicStatus": PUBLIC_TICKET_STATUS_PUBLISHED,
                PUBLIC_SORT_KEY: build_public_sort_key(ticket),
                "ticketId": ticket.ticket_id,
            }
        )
        if cursor is None:  # pragma: no cover - all fields above are present
            raise ValueError("Unable to create public ticket cursor.")
        return cursor

    def patch_fields(
        self,
        ticket_id: str,
        fields: dict[str, object],
        expected_updated_at: str | None = None,
        expected_municipality_id: str | None = None,
        expected_department_id: str | None = None,
        require_assignment_scope: bool = False,
    ) -> StoredTicket | None:
        """Apply a partial attribute update so concurrent writers do not clobber each other."""
        expression, names, values = build_update_expression(fields)
        if require_assignment_scope:
            condition = append_ticket_assignment_scope_condition(
                names,
                values,
                expected_updated_at=expected_updated_at,
                expected_municipality_id=expected_municipality_id,
                expected_department_id=expected_department_id,
            )
        elif expected_updated_at is None:
            condition = "attribute_exists(ticketId)"
        else:
            condition = "attribute_exists(ticketId) AND updatedAt = :expectedUpdatedAt"
            values[":expectedUpdatedAt"] = expected_updated_at
        update_kwargs: dict[str, object] = {
            "Key": {"ticketId": ticket_id},
            "UpdateExpression": expression,
            "ConditionExpression": condition,
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

    def claim_image_redaction(
        self, ticket_id: str, generation: int, claim_token: str, updated_at: str
    ) -> StoredTicket | None:
        try:
            response = self._tickets_table.update_item(
                Key={"ticketId": ticket_id},
                UpdateExpression=(
                    "SET imageRedactionStatus=:processing, "
                    "imageRedactionClaimToken=:token, updatedAt=:updated"
                ),
                ConditionExpression=(
                    "imageRedactionStatus=:pending AND imageRedactionGeneration=:generation"
                ),
                ExpressionAttributeValues={
                    ":processing": "processing",
                    ":pending": "pending",
                    ":token": claim_token,
                    ":updated": updated_at,
                    ":generation": generation,
                },
                ReturnValues="ALL_NEW",
            )
            return item_to_ticket(response["Attributes"])
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise

    def finalize_image_redaction(
        self, ticket_id: str, generation: int, claim_token: str, fields: dict[str, object]
    ) -> StoredTicket | None:
        expression, names, values = build_update_expression(
            {**fields, "image_redaction_claim_token": None}
        )
        names.update(
            {
                "#rs": "imageRedactionStatus",
                "#rg": "imageRedactionGeneration",
                "#rt": "imageRedactionClaimToken",
            }
        )
        values.update(
            {":processing": "processing", ":generation": generation, ":token": claim_token}
        )
        try:
            response = self._tickets_table.update_item(
                Key={"ticketId": ticket_id},
                UpdateExpression=expression,
                ConditionExpression="#rs=:processing AND #rg=:generation AND #rt=:token",
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=prepare_dynamodb_value(values),
                ReturnValues="ALL_NEW",
            )
            return item_to_ticket(response["Attributes"])
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise

    def requeue_image_redaction(
        self, ticket_id: str, generation: int, claim_token: str, updated_at: str
    ) -> StoredTicket | None:
        try:
            response = self._tickets_table.update_item(
                Key={"ticketId": ticket_id},
                UpdateExpression=(
                    "SET imageRedactionStatus=:pending, updatedAt=:updated "
                    "REMOVE imageRedactionClaimToken"
                ),
                ConditionExpression=(
                    "imageRedactionStatus=:processing AND imageRedactionGeneration=:generation "
                    "AND imageRedactionClaimToken=:token"
                ),
                ExpressionAttributeValues={
                    ":pending": "pending",
                    ":processing": "processing",
                    ":updated": updated_at,
                    ":generation": generation,
                    ":token": claim_token,
                },
                ReturnValues="ALL_NEW",
            )
            return item_to_ticket(response["Attributes"])
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise

    def start_image_reprocessing(
        self,
        ticket_id: str,
        updated_at: str,
        *,
        expected_municipality_id: str | None,
        expected_department_id: str | None,
    ) -> StoredTicket | None:
        names: dict[str, str] = {}
        values: dict[str, Any] = {
            ":pending": "pending",
            ":updated": updated_at,
            ":one": 1,
            ":zero": 0,
        }
        scope = append_ticket_access_scope_condition(
            names,
            values,
            expected_municipality_id=expected_municipality_id,
            expected_department_id=expected_department_id,
        )
        try:
            response = self._tickets_table.update_item(
                Key={"ticketId": ticket_id},
                UpdateExpression=(
                    "SET imageRedactionStatus=:pending, updatedAt=:updated, "
                    "imageRedactionGeneration=if_not_exists(imageRedactionGeneration,:one)+:one, "
                    "imageRedactionCandidateRevision=:zero "
                    "REMOVE imageRedactionClaimToken, imageRedactionCompletedAt, "
                    "imageRedactionReasonCode, imageRedactionCandidateObjectKey, "
                    "imageRedactionRegions"
                ),
                ConditionExpression=f"attribute_exists(ticketId) AND {scope}",
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=prepare_dynamodb_value(values),
                ReturnValues="ALL_NEW",
            )
            return item_to_ticket(response["Attributes"])
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise

    def apply_image_redaction_review(
        self,
        ticket_id: str,
        *,
        expected_generation: int,
        expected_status: str,
        expected_candidate_revision: int,
        expected_municipality_id: str | None,
        expected_department_id: str | None,
        fields: dict[str, Any],
        copy_candidate_to_public: bool = False,
    ) -> StoredTicket | None:
        patch_fields = dict(fields)
        if copy_candidate_to_public:
            patch_fields.pop("public_image_object_key", None)
        expression, names, values = build_update_expression(patch_fields)
        condition = append_redaction_review_condition(
            names,
            values,
            expected_status=expected_status,
            expected_generation=expected_generation,
            expected_candidate_revision=expected_candidate_revision,
            expected_municipality_id=expected_municipality_id,
            expected_department_id=expected_department_id,
        )
        if copy_candidate_to_public:
            names["#pub"] = "publicImageObjectKey"
            names["#cand"] = "imageRedactionCandidateObjectKey"
            if expression.startswith("SET "):
                expression = "SET #pub = #cand, " + expression[4:]
            elif expression:
                expression = "SET #pub = #cand " + expression
            else:
                expression = "SET #pub = #cand"
        try:
            response = self._tickets_table.update_item(
                Key={"ticketId": ticket_id},
                UpdateExpression=expression,
                ConditionExpression=condition,
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=prepare_dynamodb_value(values),
                ReturnValues="ALL_NEW",
            )
            return item_to_ticket(response["Attributes"])
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise

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


def _staff_query_target(
    *,
    browse_mode: Literal["admin", "municipality"],
    municipality_id: str | None,
    department_id: str | None,
) -> tuple[str, str, str]:
    if department_id and browse_mode == "municipality":
        return DEPARTMENT_STAFF_INDEX, "departmentId", department_id
    if browse_mode == "admin":
        return ADMIN_BROWSE_INDEX, ADMIN_BROWSE_KEY, ADMIN_BROWSE_ALL
    if not municipality_id:
        raise ValueError("municipality_id is required for municipality browse mode.")
    return STAFF_SCOPE_INDEX, STAFF_SCOPE_KEY, municipality_id


def _staff_filter_expression(
    *,
    status: str | None,
    category: str | None,
    urgency: str | None,
    department_id: str | None,
    department_ids: list[str] | None,
    assignment_state: Literal["assigned", "unassigned"] | None = None,
    q: str | None = None,
    open_only: bool = False,
):
    expression = None
    if status is not None:
        expression = Attr("status").eq(status)
    elif open_only:
        expression = Attr("status").is_in(["SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS"])
    if category is not None:
        clause = Attr("category").eq(category)
        expression = clause if expression is None else expression & clause
    if urgency is not None:
        clause = Attr("priority").eq(urgency)
        expression = clause if expression is None else expression & clause
    if assignment_state == "unassigned":
        clause = Attr("departmentId").not_exists()
        expression = clause if expression is None else expression & clause
    elif assignment_state == "assigned":
        clause = Attr("departmentId").exists()
        expression = clause if expression is None else expression & clause
    if department_id is not None:
        clause = Attr("departmentId").eq(department_id)
        expression = clause if expression is None else expression & clause
    elif department_ids is not None and assignment_state is None:
        # Unassigned tickets are visible to municipal staff; keep them when dept-scoped.
        allowed = list(department_ids)
        if allowed:
            clause = Attr("departmentId").is_in(allowed) | Attr("departmentId").not_exists()
        else:
            clause = Attr("departmentId").not_exists()
        expression = clause if expression is None else expression & clause
    if q is not None:
        # Bounded contains match — keeps search on the indexed collection path.
        search = (
            Attr("ticketNumber").contains(q)
            | Attr("ticketId").contains(q)
            | Attr("description").contains(q)
            | Attr("location.addressText").contains(q)
        )
        expression = search if expression is None else expression & search
    return expression


def _municipal_post_filter(
    ticket: StoredTicket,
    *,
    municipality_id: str | None,
    department_ids: list[str] | None,
    department_id: str | None,
) -> bool:
    if ticket.municipality_id is not None and ticket.municipality_id != municipality_id:
        return False
    if department_id is not None:
        return ticket.department_id == department_id
    if ticket.department_id is None:
        return True
    return ticket.department_id in set(department_ids or [])


def _synthetic_staff_start_key(
    ticket: StoredTicket,
    *,
    index_name: str,
    hash_name: str,
    hash_value: str,
) -> dict[str, str]:
    sort_key = f"{ticket.created_at}#{ticket.ticket_id}"
    key = {
        hash_name: hash_value,
        STAFF_SORT_KEY: sort_key,
        "ticketId": ticket.ticket_id,
    }
    if index_name == DEPARTMENT_STAFF_INDEX and ticket.department_id:
        key["departmentId"] = ticket.department_id
    return key


def _encode_staff_cursor(last_key: dict[str, Any] | None, *, index_name: str) -> str | None:
    if not last_key:
        return None
    payload = {
        "indexName": index_name,
        "ticketId": last_key.get("ticketId"),
        "staffSortKey": last_key.get(STAFF_SORT_KEY),
        "staffScopeKey": last_key.get(STAFF_SCOPE_KEY),
        "adminBrowseKey": last_key.get(ADMIN_BROWSE_KEY),
        "departmentId": last_key.get("departmentId"),
    }
    if not isinstance(payload["ticketId"], str) or not isinstance(payload["staffSortKey"], str):
        raise ValueError("Invalid staff ticket cursor.")
    raw = json.dumps(
        {key: value for key, value in payload.items() if value is not None},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_staff_cursor(
    cursor: str,
    *,
    index_name: str,
    hash_name: str,
    hash_value: str,
) -> dict[str, str]:
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid staff ticket cursor.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid staff ticket cursor.")
    if payload.get("indexName") not in {None, index_name}:
        raise ValueError("Invalid staff ticket cursor.")
    ticket_id = payload.get("ticketId")
    sort_key = payload.get("staffSortKey")
    if not isinstance(ticket_id, str) or not isinstance(sort_key, str):
        raise ValueError("Invalid staff ticket cursor.")

    start_key = {
        hash_name: hash_value,
        STAFF_SORT_KEY: sort_key,
        "ticketId": ticket_id,
    }
    # ExclusiveStartKey for GSIs must include the index hash attribute value.
    if hash_name == STAFF_SCOPE_KEY:
        start_key[STAFF_SCOPE_KEY] = hash_value
    elif hash_name == ADMIN_BROWSE_KEY:
        start_key[ADMIN_BROWSE_KEY] = hash_value
    elif hash_name == "departmentId":
        start_key["departmentId"] = hash_value
    return start_key
