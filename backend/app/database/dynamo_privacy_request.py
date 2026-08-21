"""DynamoDB privacy-request audit store (issue #321)."""

from __future__ import annotations

import logging

from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.schemas.stored_privacy_request import StoredPrivacyRequestAudit

logger = logging.getLogger(__name__)


def _is_missing_table(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") == "ResourceNotFoundException"


class DynamoPrivacyRequestAuditStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        resource = create_dynamodb_resource(self._settings)
        self._table = resource.Table(
            build_table_name(self._settings.dynamodb_table_prefix, "privacy-request-audit")
        )

    def append(self, entry: StoredPrivacyRequestAudit) -> None:
        self._table.put_item(Item=entry.model_dump(by_alias=True, exclude_none=True))

    def list_recent(self, *, limit: int = 100) -> list[StoredPrivacyRequestAudit]:
        try:
            response = self._table.scan(Limit=200)
        except ClientError as error:
            if _is_missing_table(error):
                logger.warning("Privacy-request audit table is missing; returning no rows.")
                return []
            raise
        items = [
            StoredPrivacyRequestAudit.model_validate(item) for item in response.get("Items", [])
        ]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items[: max(1, min(limit, 200))]

    def clear(self) -> None:
        raise NotImplementedError("Use db-reset for DynamoDB-backed privacy request stores.")
