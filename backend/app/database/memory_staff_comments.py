from app.schemas.staff_comment import StoredStaffComment


class InMemoryStaffCommentStore:
    def __init__(self) -> None:
        self._entries: dict[str, list[StoredStaffComment]] = {}

    def append(self, comment: StoredStaffComment) -> None:
        self._entries.setdefault(comment.ticket_id, []).append(comment)

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredStaffComment]:
        return sorted(
            self._entries.get(ticket_id, []), key=lambda item: (item.created_at, item.comment_id)
        )

    def clear(self) -> None:
        self._entries.clear()


staff_comment_store = InMemoryStaffCommentStore()
