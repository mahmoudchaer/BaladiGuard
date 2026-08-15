"""Municipal resolution-feedback review queue protocol (issue #248)."""

from __future__ import annotations

from typing import Protocol

from app.schemas.resolution_feedback import StoredResolutionReview


class ResolutionReviewStore(Protocol):
    def save(self, review: StoredResolutionReview) -> StoredResolutionReview: ...

    def get_by_ticket_id(self, ticket_id: str) -> StoredResolutionReview | None: ...

    def list_pending(self, *, municipality_id: str | None) -> list[StoredResolutionReview]: ...

    def delete(self, ticket_id: str) -> None: ...

    def clear(self) -> None: ...
