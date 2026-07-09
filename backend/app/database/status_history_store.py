from typing import Protocol

from app.schemas.stored_status_history import StoredStatusHistory


class StatusHistoryStore(Protocol):
    def append(self, entry: StoredStatusHistory) -> None: ...

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredStatusHistory]: ...

    def clear(self) -> None: ...
