from app.schemas.stored_status_history import StoredStatusHistory


class InMemoryStatusHistoryStore:
    def __init__(self) -> None:
        self._entries: dict[str, list[StoredStatusHistory]] = {}

    def append(self, entry: StoredStatusHistory) -> None:
        ticket_entries = self._entries.setdefault(entry.ticket_id, [])
        ticket_entries.append(entry)

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredStatusHistory]:
        return sorted(self._entries.get(ticket_id, []), key=lambda entry: entry.created_at)

    def clear(self) -> None:
        self._entries.clear()


status_history_store = InMemoryStatusHistoryStore()
