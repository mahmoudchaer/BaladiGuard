"""In-memory workforce directory (issue #245)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from threading import RLock
from typing import TypeVar

from app.schemas.workforce import StoredTeam, StoredWorker

T = TypeVar("T")


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _eligible(active: bool, department_ids: list[str], department_id: str | None) -> bool:
    if not active:
        return False
    if department_id and department_id not in department_ids:
        return False
    return True


class InMemoryWorkforceStore:
    def __init__(self) -> None:
        self._workers: dict[str, StoredWorker] = {}
        self._teams: dict[str, StoredTeam] = {}
        self._lock = RLock()

    def run_exclusive(self, callback: Callable[[], T]) -> T:
        with self._lock:
            return callback()

    def save_worker(self, worker: StoredWorker) -> StoredWorker:
        with self._lock:
            self._workers[worker.worker_id] = worker
            return worker

    def get_worker(self, worker_id: str) -> StoredWorker | None:
        with self._lock:
            return self._workers.get(worker_id)

    def list_workers(self, municipality_id: str | None = None) -> list[StoredWorker]:
        with self._lock:
            workers = list(self._workers.values())
        if municipality_id:
            workers = [worker for worker in workers if worker.municipality_id == municipality_id]
        return sorted(workers, key=lambda item: (item.display_name.lower(), item.worker_id))

    def save_team(self, team: StoredTeam) -> StoredTeam:
        with self._lock:
            self._teams[team.team_id] = team
            return team

    def get_team(self, team_id: str) -> StoredTeam | None:
        with self._lock:
            return self._teams.get(team_id)

    def list_teams(self, municipality_id: str | None = None) -> list[StoredTeam]:
        with self._lock:
            teams = list(self._teams.values())
        if municipality_id:
            teams = [team for team in teams if team.municipality_id == municipality_id]
        return sorted(teams, key=lambda item: (item.display_name.lower(), item.team_id))

    def claim_worker(
        self, worker_id: str, expected_updated_at: str, department_id: str | None
    ) -> bool:
        with self._lock:
            worker = self._workers.get(worker_id)
            if (
                worker is None
                or worker.updated_at != expected_updated_at
                or not _eligible(worker.active, worker.department_ids, department_id)
            ):
                return False
            self._workers[worker_id] = worker.model_copy(update={"updated_at": _iso_now()})
            return True

    def claim_team(self, team_id: str, expected_updated_at: str, department_id: str | None) -> bool:
        with self._lock:
            team = self._teams.get(team_id)
            if (
                team is None
                or team.updated_at != expected_updated_at
                or not _eligible(team.active, team.department_ids, department_id)
            ):
                return False
            self._teams[team_id] = team.model_copy(update={"updated_at": _iso_now()})
            return True

    def clear(self) -> None:
        with self._lock:
            self._workers.clear()
            self._teams.clear()


workforce_store = InMemoryWorkforceStore()
