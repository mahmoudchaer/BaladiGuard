from decimal import Decimal
from typing import Any

from app.schemas.stored_ticket import StoredTicket

OWNER_HISTORY_SORT_KEY = "ownerHistorySortKey"
PUBLIC_SORT_KEY = "publicSortKey"
PUBLIC_TICKET_STATUS_PUBLISHED = "PUBLISHED"
PUBLIC_INDEX_FIELDS = frozenset(
    {
        "final_category",
        "public_status",
        "public_description",
        "public_location_label",
        "public_published_at",
    }
)


def build_owner_history_sort_key(ticket: StoredTicket) -> str:
    return f"{ticket.created_at}#{ticket.ticket_id}"


def is_public_ticket_publishable(ticket: StoredTicket) -> bool:
    return (
        ticket.public_status == PUBLIC_TICKET_STATUS_PUBLISHED
        and bool(ticket.final_category)
        and bool(ticket.public_description and ticket.public_description.strip())
        and bool(ticket.public_location_label and ticket.public_location_label.strip())
        and bool(ticket.public_published_at)
    )


def build_public_sort_key(ticket: StoredTicket) -> str:
    published_at = ticket.public_published_at or ticket.updated_at or ticket.created_at
    return f"{published_at}#{ticket.ticket_number}"


def convert_decimals(value: Any) -> Any:
    if isinstance(value, list):
        return [convert_decimals(item) for item in value]
    if isinstance(value, dict):
        return {key: convert_decimals(item) for key, item in value.items()}
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    return value


def prepare_dynamodb_value(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: prepare_dynamodb_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [prepare_dynamodb_value(item) for item in value]
    return value


def ticket_to_item(ticket: StoredTicket) -> dict[str, Any]:
    item = ticket.model_dump(by_alias=True, mode="json")
    if ticket.owner_user_id:
        item[OWNER_HISTORY_SORT_KEY] = build_owner_history_sort_key(ticket)
    if is_public_ticket_publishable(ticket):
        item[PUBLIC_SORT_KEY] = build_public_sort_key(ticket)
    filtered = {key: value for key, value in item.items() if value is not None}
    return prepare_dynamodb_value(filtered)


def item_to_ticket(item: dict[str, Any]) -> StoredTicket:
    return StoredTicket.model_validate(convert_decimals(item))
