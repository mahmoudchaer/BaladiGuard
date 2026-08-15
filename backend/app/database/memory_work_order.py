"""In-memory work-order store (issue #247)."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import TypeVar

from app.schemas.work_order import StoredWorkOrder, is_active_work_order_state

T = TypeVar("T")


class InMemoryWorkOrderStore:
    def __init__(self) -> None:
        self._items: dict[str, StoredWorkOrder] = {}
        self._lock = RLock()

    def run_exclusive(self, callback: Callable[[], T]) -> T:
        with self._lock:
            return callback()

    def save(self, work_order: StoredWorkOrder) -> StoredWorkOrder:
        with self._lock:
            self._items[work_order.work_order_id] = work_order
            return work_order

    def get(self, work_order_id: str) -> StoredWorkOrder | None:
        with self._lock:
            return self._items.get(work_order_id)

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredWorkOrder]:
        with self._lock:
            items = [item for item in self._items.values() if item.ticket_id == ticket_id]
        return sorted(items, key=lambda item: (item.created_at, item.work_order_id))

    def find_active_for_ticket(self, ticket_id: str) -> StoredWorkOrder | None:
        active = [
            item
            for item in self.list_by_ticket_id(ticket_id)
            if is_active_work_order_state(item.state)
        ]
        if not active:
            return None
        return sorted(active, key=lambda item: (item.created_at, item.work_order_id))[0]

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


work_order_store = InMemoryWorkOrderStore()
