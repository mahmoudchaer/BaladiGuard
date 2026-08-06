from app.schemas.stored_account_audit import StoredAccountAudit


class InMemoryAccountAuditStore:
    def __init__(self) -> None:
        self._entries: list[StoredAccountAudit] = []

    def append(self, entry: StoredAccountAudit) -> None:
        self._entries.append(entry)

    def list_by_target_staff_id(self, target_staff_id: str) -> list[StoredAccountAudit]:
        return sorted(
            [entry for entry in self._entries if entry.target_staff_id == target_staff_id],
            key=lambda entry: entry.created_at,
        )

    def list_all(self) -> list[StoredAccountAudit]:
        return sorted(self._entries, key=lambda entry: entry.created_at)

    def clear(self) -> None:
        self._entries.clear()


account_audit_store = InMemoryAccountAuditStore()
