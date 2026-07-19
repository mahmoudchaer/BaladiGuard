from app.schemas.stored_duplicate_group import StoredDuplicateGroup


class InMemoryDuplicateGroupStore:
    def __init__(self) -> None:
        self._groups: dict[str, StoredDuplicateGroup] = {}

    def save(self, group: StoredDuplicateGroup) -> None:
        self._groups[group.duplicate_group_id] = group

    def get(self, duplicate_group_id: str) -> StoredDuplicateGroup | None:
        return self._groups.get(duplicate_group_id)

    def clear(self) -> None:
        self._groups.clear()


duplicate_group_store = InMemoryDuplicateGroupStore()
