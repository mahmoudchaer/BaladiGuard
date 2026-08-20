"""Municipality profile store protocol (issue #322)."""

from __future__ import annotations

from typing import Protocol

from app.schemas.stored_municipality import StoredMunicipality


class MunicipalityStore(Protocol):
    def get(self, municipality_id: str) -> StoredMunicipality | None: ...

    def list_all(self) -> list[StoredMunicipality]: ...

    def put(self, profile: StoredMunicipality) -> StoredMunicipality: ...

    def clear(self) -> None: ...
