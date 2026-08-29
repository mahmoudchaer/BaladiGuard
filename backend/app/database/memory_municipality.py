"""In-memory municipality profiles, seeded from JSON (issue #322)."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from app.schemas.stored_municipality import StoredMunicipality

SEEDS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "db" / "seeds"


def load_seed_municipalities() -> list[StoredMunicipality]:
    raw = json.loads((SEEDS_DIR / "municipalities.json").read_text(encoding="utf-8"))
    return [StoredMunicipality.model_validate(item) for item in raw]


class InMemoryMunicipalityStore:
    def __init__(self) -> None:
        self._items: dict[str, StoredMunicipality] = {}
        self._lock = Lock()
        self.reset_from_seed()

    def reset_from_seed(self) -> None:
        with self._lock:
            self._items = {
                item.municipality_id: item.model_copy(deep=True)
                for item in load_seed_municipalities()
            }

    def get(self, municipality_id: str) -> StoredMunicipality | None:
        with self._lock:
            item = self._items.get(municipality_id)
            return item.model_copy(deep=True) if item else None

    def list_all(self) -> list[StoredMunicipality]:
        with self._lock:
            items = [item.model_copy(deep=True) for item in self._items.values()]
        items.sort(key=lambda item: item.name.lower())
        return items

    def put(self, profile: StoredMunicipality) -> StoredMunicipality:
        stored = profile.model_copy(deep=True)
        with self._lock:
            self._items[stored.municipality_id] = stored
        return stored.model_copy(deep=True)

    def clear(self) -> None:
        self.reset_from_seed()


municipality_store = InMemoryMunicipalityStore()
