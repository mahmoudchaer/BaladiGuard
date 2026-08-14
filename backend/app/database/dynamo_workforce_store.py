"""DynamoDB workforce directory (issue #245)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import convert_decimals, prepare_dynamodb_value
from app.schemas.workforce import StoredTeam, StoredWorker

T = TypeVar("T")


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class DynamoWorkforceStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        resource = create_dynamodb_resource(self._settings)
        prefix = self._settings.dynamodb_table_prefix
        self._workers = resource.Table(build_table_name(prefix, "workforce-workers"))
        self._teams = resource.Table(build_table_name(prefix, "workforce-teams"))

    def run_exclusive(self, callback: Callable[[], T]) -> T:
        return callback()

    def save_worker(self, worker: StoredWorker) -> StoredWorker:
        self._workers.put_item(
            Item=prepare_dynamodb_value(worker.model_dump(by_alias=True, mode="json"))
        )
        return worker

    def get_worker(self, worker_id: str) -> StoredWorker | None:
        response = self._workers.get_item(Key={"workerId": worker_id}, ConsistentRead=True)
        item = response.get("Item")
        return StoredWorker.model_validate(convert_decimals(item)) if item else None

    def list_workers(self, municipality_id: str | None = None) -> list[StoredWorker]:
        items = _query_or_scan(self._workers, "municipalityId", municipality_id)
        workers = [StoredWorker.model_validate(convert_decimals(item)) for item in items]
        return sorted(workers, key=lambda item: (item.display_name.lower(), item.worker_id))

    def save_team(self, team: StoredTeam) -> StoredTeam:
        self._teams.put_item(
            Item=prepare_dynamodb_value(team.model_dump(by_alias=True, mode="json"))
        )
        return team

    def get_team(self, team_id: str) -> StoredTeam | None:
        response = self._teams.get_item(Key={"teamId": team_id}, ConsistentRead=True)
        item = response.get("Item")
        return StoredTeam.model_validate(convert_decimals(item)) if item else None

    def list_teams(self, municipality_id: str | None = None) -> list[StoredTeam]:
        items = _query_or_scan(self._teams, "municipalityId", municipality_id)
        teams = [StoredTeam.model_validate(convert_decimals(item)) for item in items]
        return sorted(teams, key=lambda item: (item.display_name.lower(), item.team_id))

    def claim_worker(
        self, worker_id: str, expected_updated_at: str, department_id: str | None
    ) -> bool:
        return _claim_assignee(
            self._workers,
            key={"workerId": worker_id},
            expected_updated_at=expected_updated_at,
            department_id=department_id,
        )

    def claim_team(self, team_id: str, expected_updated_at: str, department_id: str | None) -> bool:
        return _claim_assignee(
            self._teams,
            key={"teamId": team_id},
            expected_updated_at=expected_updated_at,
            department_id=department_id,
        )

    def clear(self) -> None:
        raise NotImplementedError("DynamoWorkforceStore does not support clear().")


def _claim_assignee(
    table,
    *,
    key: dict[str, str],
    expected_updated_at: str,
    department_id: str | None,
) -> bool:
    condition = Attr("updatedAt").eq(expected_updated_at) & Attr("active").eq(True)
    if department_id:
        condition = condition & Attr("departmentIds").contains(department_id)
    try:
        table.update_item(
            Key=key,
            UpdateExpression="SET updatedAt = :now",
            ExpressionAttributeValues={":now": _iso_now()},
            ConditionExpression=condition,
        )
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        return False


def _query_or_scan(table, key_name: str, municipality_id: str | None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if municipality_id:
        kwargs: dict[str, Any] = {
            "IndexName": "municipalityId-index",
            "KeyConditionExpression": Key(key_name).eq(municipality_id),
        }
        while True:
            response = table.query(**kwargs)
            items.extend(response.get("Items") or [])
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                return items
            kwargs["ExclusiveStartKey"] = last_key
    kwargs = {}
    while True:
        response = table.scan(**kwargs)
        items.extend(response.get("Items") or [])
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return items
        kwargs["ExclusiveStartKey"] = last_key
