from typing import Any

from app.schemas.stored_duplicate_group import StoredDuplicateGroup


def duplicate_group_to_item(group: StoredDuplicateGroup) -> dict[str, Any]:
    return group.model_dump(by_alias=True, mode="json")


def item_to_duplicate_group(item: dict[str, Any]) -> StoredDuplicateGroup:
    return StoredDuplicateGroup.model_validate(item)
