"""DynamoDB municipality profiles (issue #322)."""

from __future__ import annotations

import logging
from typing import Any

from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import convert_decimals, prepare_dynamodb_value
from app.schemas.stored_municipality import StoredMunicipality

logger = logging.getLogger(__name__)


def _is_missing_table(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") == "ResourceNotFoundException"


class DynamoMunicipalityStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        resource = create_dynamodb_resource(self._settings)
        self._table = resource.Table(
            build_table_name(self._settings.dynamodb_table_prefix, "municipalities")
        )

    def get(self, municipality_id: str) -> StoredMunicipality | None:
        try:
            response = self._table.get_item(Key={"municipalityId": municipality_id})
        except ClientError as error:
            if _is_missing_table(error):
                logger.warning("Municipalities table is missing; returning no profile.")
                return None
            raise
        item = response.get("Item")
        if not item:
            return None
        return StoredMunicipality.model_validate(convert_decimals(item))

    def list_all(self) -> list[StoredMunicipality]:
        items: list[StoredMunicipality] = []
        start = None
        pages = 0
        while pages < 8:
            kwargs: dict[str, Any] = {"Limit": 100}
            if start:
                kwargs["ExclusiveStartKey"] = start
            try:
                response = self._table.scan(**kwargs)
            except ClientError as error:
                if _is_missing_table(error):
                    logger.warning("Municipalities table is missing; returning no profiles.")
                    return []
                raise
            items.extend(
                StoredMunicipality.model_validate(convert_decimals(item))
                for item in response.get("Items", [])
            )
            pages += 1
            start = response.get("LastEvaluatedKey")
            if not start:
                break
        items.sort(key=lambda item: item.name.lower())
        return items

    def put(self, profile: StoredMunicipality) -> StoredMunicipality:
        payload = prepare_dynamodb_value(profile.model_dump(by_alias=True, exclude_none=True))
        self._table.put_item(Item=payload)
        return profile

    def clear(self) -> None:
        raise NotImplementedError("Use db-reset for DynamoDB-backed municipality stores.")
