from typing import Any

from app.schemas.stored_audit_history import StoredAuditHistory


def audit_history_to_item(entry: StoredAuditHistory) -> dict[str, Any]:
    return entry.model_dump(by_alias=True, mode="json")


def item_to_audit_history(item: dict[str, Any]) -> StoredAuditHistory:
    return StoredAuditHistory.model_validate(item)
