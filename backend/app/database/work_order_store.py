"""Work-order store protocol (issue #247)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

from app.schemas.work_order import StoredWorkOrder

T = TypeVar("T")


class WorkOrderStore(Protocol):
    def run_exclusive(self, callback: Callable[[], T]) -> T: ...

    def save(self, work_order: StoredWorkOrder) -> StoredWorkOrder: ...

    def get(self, work_order_id: str) -> StoredWorkOrder | None: ...

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredWorkOrder]: ...

    def find_active_for_ticket(self, ticket_id: str) -> StoredWorkOrder | None: ...

    def clear(self) -> None: ...
