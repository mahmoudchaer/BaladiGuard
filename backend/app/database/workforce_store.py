"""Workforce directory store protocol (issue #245)."""

from __future__ import annotations

from typing import Protocol

from app.schemas.workforce import StoredTeam, StoredWorker


class WorkforceNotFoundError(LookupError):
    pass


class WorkforceStore(Protocol):
    def save_worker(self, worker: StoredWorker) -> StoredWorker: ...

    def get_worker(self, worker_id: str) -> StoredWorker | None: ...

    def list_workers(self, municipality_id: str | None = None) -> list[StoredWorker]: ...

    def save_team(self, team: StoredTeam) -> StoredTeam: ...

    def get_team(self, team_id: str) -> StoredTeam | None: ...

    def list_teams(self, municipality_id: str | None = None) -> list[StoredTeam]: ...

    def clear(self) -> None: ...
