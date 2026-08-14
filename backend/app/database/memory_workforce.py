"""In-memory workforce directory (issue #245)."""

from __future__ import annotations

from threading import Lock

from app.schemas.workforce import StoredTeam, StoredWorker


class InMemoryWorkforceStore:
    def __init__(self) -> None:
        self._workers: dict[str, StoredWorker] = {}
        self._teams: dict[str, StoredTeam] = {}
        self._lock = Lock()

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

    def clear(self) -> None:
        with self._lock:
            self._workers.clear()
            self._teams.clear()


workforce_store = InMemoryWorkforceStore()
