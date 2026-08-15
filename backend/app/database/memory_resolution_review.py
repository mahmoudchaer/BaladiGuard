"""In-memory municipal resolution-feedback review queue (issue #248)."""

from __future__ import annotations

from threading import RLock

from app.schemas.resolution_feedback import StoredResolutionReview


class InMemoryResolutionReviewStore:
    def __init__(self) -> None:
        self._items: dict[str, StoredResolutionReview] = {}
        self._lock = RLock()

    def save(self, review: StoredResolutionReview) -> StoredResolutionReview:
        with self._lock:
            self._items[review.ticket_id] = review
            return review

    def get_by_ticket_id(self, ticket_id: str) -> StoredResolutionReview | None:
        with self._lock:
            return self._items.get(ticket_id)

    def list_pending(self, *, municipality_id: str | None) -> list[StoredResolutionReview]:
        with self._lock:
            items = [
                item
                for item in self._items.values()
                if item.review_status == "PENDING"
                and (municipality_id is None or item.municipality_id == municipality_id)
            ]
        return sorted(items, key=lambda item: (item.submitted_at, item.ticket_id), reverse=True)

    def delete(self, ticket_id: str) -> None:
        with self._lock:
            self._items.pop(ticket_id, None)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


resolution_review_store = InMemoryResolutionReviewStore()
