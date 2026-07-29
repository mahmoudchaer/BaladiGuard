from app.schemas.stored_audit_history import StoredAuditHistory


class InMemoryAuditHistoryStore:
    def __init__(self) -> None:
        self._entries: dict[str, list[StoredAuditHistory]] = {}

    def append(self, entry: StoredAuditHistory) -> None:
        ticket_entries = self._entries.setdefault(entry.ticket_id, [])
        ticket_entries.append(entry)

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredAuditHistory]:
        return sorted(self._entries.get(ticket_id, []), key=lambda entry: entry.created_at)

    def clear(self) -> None:
        self._entries.clear()


audit_history_store = InMemoryAuditHistoryStore()
