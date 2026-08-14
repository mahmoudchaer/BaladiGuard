"""Workforce directory store protocol (issue #245)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

from app.schemas.stored_ticket import StoredTicket
from app.schemas.workforce import StoredTeam, StoredWorker

T = TypeVar("T")


class WorkforceNotFoundError(LookupError):
    pass


class WorkforceStore(Protocol):
    def run_exclusive(self, callback: Callable[[], T]) -> T: ...

    def save_worker(self, worker: StoredWorker) -> StoredWorker: ...

    def get_worker(self, worker_id: str) -> StoredWorker | None: ...

    def list_workers(self, municipality_id: str | None = None) -> list[StoredWorker]: ...

    def save_team(self, team: StoredTeam) -> StoredTeam: ...

    def get_team(self, team_id: str) -> StoredTeam | None: ...

    def list_teams(self, municipality_id: str | None = None) -> list[StoredTeam]: ...

    def claim_worker(
        self, worker_id: str, expected_updated_at: str, department_id: str | None
    ) -> bool: ...

    def claim_team(
        self, team_id: str, expected_updated_at: str, department_id: str | None
    ) -> bool: ...

    def commit_ticket_assignment(
        self,
        *,
        ticket_id: str,
        ticket_fields: dict[str, object],
        worker_id: str | None,
        team_id: str | None,
        department_id: str | None,
        expected_updated_at: str,
        expected_ticket_updated_at: str | None,
        expected_ticket_municipality_id: str | None,
        expected_ticket_department_id: str | None,
        apply_ticket_patch: Callable[[], StoredTicket | None],
    ) -> StoredTicket | None: ...

    def clear(self) -> None: ...
