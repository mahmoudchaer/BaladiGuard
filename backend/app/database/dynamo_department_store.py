"""DynamoDB department catalog (issue #322)."""

from __future__ import annotations

import logging
from typing import Any

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import convert_decimals, prepare_dynamodb_value
from app.schemas.stored_department import StoredDepartment

logger = logging.getLogger(__name__)


def _is_missing_table(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") == "ResourceNotFoundException"


class DynamoDepartmentStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        resource = create_dynamodb_resource(self._settings)
        self._table = resource.Table(
            build_table_name(self._settings.dynamodb_table_prefix, "departments")
        )

    def get(self, department_id: str) -> StoredDepartment | None:
        try:
            response = self._table.get_item(Key={"departmentId": department_id})
        except ClientError as error:
            if _is_missing_table(error):
                logger.warning("Departments table is missing; returning no department.")
                return None
            raise
        item = response.get("Item")
        if not item:
            return None
        return StoredDepartment.model_validate(convert_decimals(item))

    def list_all(self) -> list[StoredDepartment]:
        items: list[StoredDepartment] = []
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
                    logger.warning("Departments table is missing; returning no departments.")
                    return []
                raise
            items.extend(
                StoredDepartment.model_validate(convert_decimals(item))
                for item in response.get("Items", [])
            )
            pages += 1
            start = response.get("LastEvaluatedKey")
            if not start:
                break
        items.sort(key=lambda item: (item.municipality_id, item.name.lower()))
        return items

    def list_by_municipality(self, municipality_id: str) -> list[StoredDepartment]:
        items: list[StoredDepartment] = []
        kwargs: dict[str, Any] = {
            "IndexName": "municipalityId-index",
            "KeyConditionExpression": Key("municipalityId").eq(municipality_id),
        }
        pages = 0
        while pages < 8:
            try:
                response = self._table.query(**kwargs)
            except ClientError as error:
                if _is_missing_table(error):
                    logger.warning("Departments table is missing; returning no departments.")
                    return []
                raise
            items.extend(
                StoredDepartment.model_validate(convert_decimals(item))
                for item in response.get("Items", [])
            )
            pages += 1
            start = response.get("LastEvaluatedKey")
            if not start:
                break
            kwargs["ExclusiveStartKey"] = start
        items.sort(key=lambda item: item.name.lower())
        return items

    def put(self, department: StoredDepartment) -> StoredDepartment:
        payload = prepare_dynamodb_value(department.model_dump(by_alias=True, exclude_none=True))
        self._table.put_item(Item=payload)
        return department

    def clear(self) -> None:
        raise NotImplementedError("Use db-reset for DynamoDB-backed department stores.")
