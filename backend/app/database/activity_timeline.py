"""Chronological activity keys and bounded timeline page reads."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from boto3.dynamodb.conditions import Key

TICKET_ID_INDEX = "ticketId-index"
TICKET_TIMELINE_INDEX = "ticketTimeline-index"

T = TypeVar("T")


def build_timeline_key(kind: str, item_id: str, created_at: str) -> str:
    return f"{created_at}#{kind}:{item_id}"


def item_timeline_key(item: dict[str, Any], *, kind: str, id_field: str) -> str | None:
    existing = item.get("timelineKey")
    if isinstance(existing, str) and existing:
        return existing
    item_id = item.get(id_field)
    created_at = item.get("createdAt")
    if isinstance(item_id, str) and isinstance(created_at, str):
        return build_timeline_key(kind, item_id, created_at)
    return None


def _query_all_pages(
    table: Any,
    *,
    index_name: str,
    key_condition: Any,
    filter_expression: Any | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {
        "IndexName": index_name,
        "KeyConditionExpression": key_condition,
    }
    if filter_expression is not None:
        kwargs["FilterExpression"] = filter_expression
    while True:
        response = table.query(**kwargs)
        items.extend(response.get("Items") or [])
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return items
        kwargs["ExclusiveStartKey"] = last_key


def _query_gsi_page(
    table: Any,
    *,
    ticket_id: str,
    limit: int,
    cursor: str | None,
) -> tuple[list[dict[str, Any]], bool]:
    key_condition = Key("ticketId").eq(ticket_id)
    if cursor:
        key_condition = key_condition & Key("timelineKey").gt(cursor)
    response = table.query(
        IndexName=TICKET_TIMELINE_INDEX,
        KeyConditionExpression=key_condition,
        Limit=limit,
    )
    items = list(response.get("Items") or [])
    return items, bool(response.get("LastEvaluatedKey"))


def list_ticket_timeline_page(
    table: Any,
    *,
    ticket_id: str,
    limit: int,
    exclusive_start_key: dict[str, Any] | None,
    kind: str,
    id_field: str,
    from_item: Callable[[dict[str, Any]], T],
    use_gsi: bool,
) -> tuple[list[T], dict[str, Any] | None]:
    """Return a keyset page from the cutover GSI or the pre-cutover compatibility path.

    After ``ACTIVITY_TIMELINE_USE_GSI=true``, only ``ticketTimeline-index`` is
    queried. Leftover unkeyed rows are the compatibility path's job, used only
    while the flag is still off.
    """
    if exclusive_start_key and exclusive_start_key.get("done"):
        return [], None
    cursor = exclusive_start_key.get("timelineKey") if exclusive_start_key else None
    if cursor is not None and not isinstance(cursor, str):
        cursor = None

    if use_gsi:
        items, has_more = _query_gsi_page(table, ticket_id=ticket_id, limit=limit, cursor=cursor)
        next_key = None
        if items and has_more:
            last_key = items[-1].get("timelineKey")
            if isinstance(last_key, str):
                next_key = {"timelineKey": last_key}
        return [from_item(item) for item in items], next_key

    combined = _query_all_pages(
        table,
        index_name=TICKET_ID_INDEX,
        key_condition=Key("ticketId").eq(ticket_id),
    )
    unique: dict[str, tuple[str, dict[str, Any]]] = {}
    for item in combined:
        key = item_timeline_key(item, kind=kind, id_field=id_field)
        item_id = item.get(id_field)
        if key is None or not isinstance(item_id, str):
            continue
        if cursor and key <= cursor:
            continue
        unique.setdefault(item_id, (key, item))

    ordered = sorted(unique.values(), key=lambda pair: pair[0])
    page = ordered[:limit]
    next_key = {"timelineKey": page[-1][0]} if page and len(ordered) > limit else None
    return [from_item(item) for _, item in page], next_key
