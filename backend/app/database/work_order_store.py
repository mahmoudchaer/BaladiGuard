"""Work-order store protocol (issue #247)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

from app.schemas.work_order import StoredWorkOrder

T = TypeVar("T")

ACTIVE_WORK_ORDER_CLAIM_PREFIX = "wo_active_"


def active_work_order_claim_id(ticket_id: str) -> str:
    return f"{ACTIVE_WORK_ORDER_CLAIM_PREFIX}{ticket_id}"


class WorkOrderTicketMissingError(Exception):
    """Raised when an atomic create cannot attach the work order to its ticket."""


class WorkOrderStore(Protocol):
    def run_exclusive(self, callback: Callable[[], T]) -> T: ...

    def save(self, work_order: StoredWorkOrder) -> StoredWorkOrder: ...

    def create_active(self, work_order: StoredWorkOrder) -> StoredWorkOrder: ...

    def save_if_state(
        self,
        work_order: StoredWorkOrder,
        *,
        expected_state: str,
        expected_updated_at: str,
        clear_active: bool = False,
    ) -> StoredWorkOrder | None: ...

    def get(self, work_order_id: str) -> StoredWorkOrder | None: ...

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredWorkOrder]: ...

    def find_active_for_ticket(self, ticket_id: str) -> StoredWorkOrder | None: ...

    def clear(self) -> None: ...
