from typing import Protocol

from app.schemas.stored_duplicate_group import StoredDuplicateGroup


class DuplicateGroupStore(Protocol):
    def save(self, group: StoredDuplicateGroup) -> None: ...

    def get(self, duplicate_group_id: str) -> StoredDuplicateGroup | None: ...

    def clear(self) -> None: ...
