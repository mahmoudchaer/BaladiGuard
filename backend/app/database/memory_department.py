"""In-memory department catalog, seeded from JSON (issue #322)."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from app.schemas.stored_department import StoredDepartment

SEEDS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "db" / "seeds"


def load_seed_departments() -> list[StoredDepartment]:
    raw = json.loads((SEEDS_DIR / "departments.json").read_text(encoding="utf-8"))
    return [StoredDepartment.model_validate(item) for item in raw]


class InMemoryDepartmentStore:
    def __init__(self) -> None:
        self._items: dict[str, StoredDepartment] = {}
        self._lock = Lock()
        self.reset_from_seed()

    def reset_from_seed(self) -> None:
        with self._lock:
            self._items = {
                item.department_id: item.model_copy(deep=True) for item in load_seed_departments()
            }

    def get(self, department_id: str) -> StoredDepartment | None:
        with self._lock:
            item = self._items.get(department_id)
            return item.model_copy(deep=True) if item else None

    def list_all(self) -> list[StoredDepartment]:
        with self._lock:
            items = [item.model_copy(deep=True) for item in self._items.values()]
        items.sort(key=lambda item: (item.municipality_id, item.name.lower()))
        return items

    def list_by_municipality(self, municipality_id: str) -> list[StoredDepartment]:
        items = [item for item in self.list_all() if item.municipality_id == municipality_id]
        items.sort(key=lambda item: item.name.lower())
        return items

    def put(self, department: StoredDepartment) -> StoredDepartment:
        stored = department.model_copy(deep=True)
        with self._lock:
            self._items[stored.department_id] = stored
        return stored.model_copy(deep=True)

    def clear(self) -> None:
        self.reset_from_seed()


department_store = InMemoryDepartmentStore()
