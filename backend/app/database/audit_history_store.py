from typing import Protocol

from app.schemas.stored_audit_history import StoredAuditHistory


class AuditHistoryStore(Protocol):
    def append(self, entry: StoredAuditHistory) -> None: ...

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredAuditHistory]: ...

    def clear(self) -> None: ...
