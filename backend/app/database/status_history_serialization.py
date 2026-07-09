from typing import Any

from app.schemas.stored_status_history import StoredStatusHistory


def status_history_to_item(entry: StoredStatusHistory) -> dict[str, Any]:
    return entry.model_dump(by_alias=True, mode="json")


def item_to_status_history(item: dict[str, Any]) -> StoredStatusHistory:
    return StoredStatusHistory.model_validate(item)
