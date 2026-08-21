"""Municipality department catalog store protocol (issue #322)."""

from __future__ import annotations

from typing import Protocol

from app.schemas.stored_department import StoredDepartment


class DepartmentStore(Protocol):
    def get(self, department_id: str) -> StoredDepartment | None: ...

    def list_all(self) -> list[StoredDepartment]: ...

    def list_by_municipality(self, municipality_id: str) -> list[StoredDepartment]: ...

    def put(self, department: StoredDepartment) -> StoredDepartment: ...

    def clear(self) -> None: ...
