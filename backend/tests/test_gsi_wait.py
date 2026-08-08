"""Bounded DynamoDB GSI waiter tests."""

from __future__ import annotations

from typing import Any

import pytest

from app.database.migrations import _wait_for_gsi


class FakeDynamoClient:
    def __init__(self, statuses: list[str | None]) -> None:
        self._statuses = list(statuses)
        self.calls = 0

    def describe_table(self, *, TableName: str) -> dict[str, Any]:
        self.calls += 1
        status = self._statuses.pop(0) if self._statuses else None
        indexes: list[dict[str, Any]] = []
        if status is not None:
            indexes.append({"IndexName": "byStatus", "IndexStatus": status})
        return {"Table": {"TableName": TableName, "GlobalSecondaryIndexes": indexes}}


def test_wait_for_gsi_returns_when_active(monkeypatch):
    client = FakeDynamoClient(["CREATING", "ACTIVE"])
    monkeypatch.setattr("app.database.migrations.time.sleep", lambda *_args, **_kwargs: None)

    _wait_for_gsi(client, "tickets", "byStatus", timeout_seconds=10, poll_seconds=0)

    assert client.calls == 2


def test_wait_for_gsi_times_out(monkeypatch):
    client = FakeDynamoClient(["CREATING", "CREATING", "CREATING"])
    monkeypatch.setattr("app.database.migrations.time.sleep", lambda *_args, **_kwargs: None)
    # Force deadline immediately after first poll by freezing monotonic progression.
    ticks = iter([0.0, 0.0, 100.0])
    monkeypatch.setattr("app.database.migrations.time.monotonic", lambda: next(ticks, 100.0))

    with pytest.raises(TimeoutError, match="Timed out waiting for GSI"):
        _wait_for_gsi(client, "tickets", "byStatus", timeout_seconds=1, poll_seconds=0)


def test_wait_for_gsi_missing_index(monkeypatch):
    client = FakeDynamoClient([None])
    monkeypatch.setattr("app.database.migrations.time.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.database.migrations.time.monotonic", lambda: 0.0)

    with pytest.raises(RuntimeError, match="was not found"):
        _wait_for_gsi(client, "tickets", "byStatus", timeout_seconds=10, poll_seconds=0)


def test_wait_for_gsi_terminal_status(monkeypatch):
    client = FakeDynamoClient(["DELETING"])
    monkeypatch.setattr("app.database.migrations.time.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.database.migrations.time.monotonic", lambda: 0.0)

    with pytest.raises(RuntimeError, match="terminal status DELETING"):
        _wait_for_gsi(client, "tickets", "byStatus", timeout_seconds=10, poll_seconds=0)
