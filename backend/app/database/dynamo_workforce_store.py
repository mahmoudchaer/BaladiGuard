"""DynamoDB workforce directory (issue #245)."""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Key

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import convert_decimals, prepare_dynamodb_value
from app.schemas.workforce import StoredTeam, StoredWorker


class DynamoWorkforceStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        resource = create_dynamodb_resource(self._settings)
        prefix = self._settings.dynamodb_table_prefix
        self._workers = resource.Table(build_table_name(prefix, "workforce-workers"))
        self._teams = resource.Table(build_table_name(prefix, "workforce-teams"))

    def save_worker(self, worker: StoredWorker) -> StoredWorker:
        self._workers.put_item(
            Item=prepare_dynamodb_value(worker.model_dump(by_alias=True, mode="json"))
        )
        return worker

    def get_worker(self, worker_id: str) -> StoredWorker | None:
        response = self._workers.get_item(Key={"workerId": worker_id})
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
        response = self._teams.get_item(Key={"teamId": team_id})
        item = response.get("Item")
        return StoredTeam.model_validate(convert_decimals(item)) if item else None

    def list_teams(self, municipality_id: str | None = None) -> list[StoredTeam]:
        items = _query_or_scan(self._teams, "municipalityId", municipality_id)
        teams = [StoredTeam.model_validate(convert_decimals(item)) for item in items]
        return sorted(teams, key=lambda item: (item.display_name.lower(), item.team_id))

    def clear(self) -> None:
        raise NotImplementedError("DynamoWorkforceStore does not support clear().")


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
