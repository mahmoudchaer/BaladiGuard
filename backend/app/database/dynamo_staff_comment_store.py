from boto3.dynamodb.conditions import Key

from app.config import Settings, get_settings
from app.database.activity_timeline import build_timeline_key, list_ticket_timeline_page
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.schemas.staff_comment import StoredStaffComment


class DynamoStaffCommentStore:
    def __init__(self, settings: Settings | None = None) -> None:
        resolved = settings or get_settings()
        self._settings = resolved
        self._resource = create_dynamodb_resource(resolved)
        self._table = self._resource.Table(
            build_table_name(resolved.dynamodb_table_prefix, "staff-comments")
        )

    def append(self, comment: StoredStaffComment) -> None:
        item = comment.model_dump(by_alias=True)
        item["timelineKey"] = build_timeline_key("comment", comment.comment_id, comment.created_at)
        self._table.put_item(Item=item)

    def list_by_ticket_id_page(
        self, ticket_id: str, *, limit: int, exclusive_start_key: dict | None = None
    ) -> tuple[list[StoredStaffComment], dict | None]:
        return list_ticket_timeline_page(
            self._table,
            ticket_id=ticket_id,
            limit=limit,
            exclusive_start_key=exclusive_start_key,
            kind="comment",
            id_field="commentId",
            from_item=StoredStaffComment.model_validate,
            use_gsi=self._settings.activity_timeline_use_gsi,
        )

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredStaffComment]:
        items = []
        query_kwargs = {
            "IndexName": "ticketId-index",
            "KeyConditionExpression": Key("ticketId").eq(ticket_id),
        }
        while True:
            response = self._table.query(**query_kwargs)
            items.extend(
                StoredStaffComment.model_validate(item) for item in response.get("Items", [])
            )
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key
        return sorted(items, key=lambda item: (item.created_at, item.comment_id))

    def clear(self) -> None:
        raise NotImplementedError("DynamoStaffCommentStore does not support clear().")
