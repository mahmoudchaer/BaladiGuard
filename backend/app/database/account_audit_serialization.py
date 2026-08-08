from typing import Any

from app.schemas.stored_account_audit import StoredAccountAudit


def account_audit_to_item(entry: StoredAccountAudit) -> dict[str, Any]:
    return entry.model_dump(by_alias=True, mode="json")


def item_to_account_audit(item: dict[str, Any]) -> StoredAccountAudit:
    return StoredAccountAudit.model_validate(item)
