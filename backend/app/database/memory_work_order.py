"""In-memory work-order store (issue #247)."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import TypeVar

from app.database.work_order_store import WorkOrderTicketMissingError
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

    def create_active(self, work_order: StoredWorkOrder) -> StoredWorkOrder:
        with self._lock:
            existing = self.find_active_for_ticket(work_order.ticket_id)
            if existing is not None:
                return existing
            self._items[work_order.work_order_id] = work_order
            patched = self._patch_ticket_pointer(
                work_order.ticket_id,
                work_order.work_order_id,
                updated_at=work_order.updated_at,
                updated_by=work_order.updated_by,
            )
            if patched is None:
                self._items.pop(work_order.work_order_id, None)
                raced = self.find_active_for_ticket(work_order.ticket_id)
                if raced is not None:
                    return raced
                raise WorkOrderTicketMissingError("Ticket was not found.")
            return work_order

    def save_if_state(
        self,
        work_order: StoredWorkOrder,
        *,
        expected_state: str,
        expected_updated_at: str,
        clear_active: bool = False,
    ) -> StoredWorkOrder | None:
        with self._lock:
            current = self._items.get(work_order.work_order_id)
            if (
                current is None
                or current.state != expected_state
                or current.updated_at != expected_updated_at
            ):
                return None
            previous = current
            self._items[work_order.work_order_id] = work_order
            if clear_active:
                from app.database.store_factory import get_ticket_store

                ticket = get_ticket_store().get(work_order.ticket_id)
                if ticket is not None and ticket.active_work_order_id not in {
                    None,
                    work_order.work_order_id,
                }:
                    self._items[work_order.work_order_id] = previous
                    return None
                if ticket is not None:
                    patched = self._patch_ticket_pointer(
                        work_order.ticket_id,
                        None,
                        updated_at=work_order.updated_at,
                        updated_by=work_order.updated_by,
                    )
                    if patched is None:
                        self._items[work_order.work_order_id] = previous
                        return None
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

    def _patch_ticket_pointer(
        self,
        ticket_id: str,
        work_order_id: str | None,
        *,
        updated_at: str,
        updated_by: str,
    ) -> object | None:
        from app.database.store_factory import get_ticket_store

        return get_ticket_store().patch_fields(
            ticket_id,
            {
                "active_work_order_id": work_order_id,
                "updated_at": updated_at,
                "updated_by": updated_by,
            },
        )


work_order_store = InMemoryWorkOrderStore()
