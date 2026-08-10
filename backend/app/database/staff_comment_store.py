from typing import Protocol

from app.schemas.staff_comment import StoredStaffComment


class StaffCommentStore(Protocol):
    def append(self, comment: StoredStaffComment) -> None: ...

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredStaffComment]: ...

    def clear(self) -> None: ...
