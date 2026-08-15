"""In-memory work-order evidence store (issue #248)."""

from __future__ import annotations

from threading import RLock

from app.schemas.work_order_evidence import StoredWorkOrderEvidence, WorkOrderEvidenceKind


class InMemoryWorkOrderEvidenceStore:
    def __init__(self) -> None:
        self._items: dict[str, StoredWorkOrderEvidence] = {}
        self._lock = RLock()

    def save(self, evidence: StoredWorkOrderEvidence) -> StoredWorkOrderEvidence:
        with self._lock:
            self._items[evidence.evidence_id] = evidence
            return evidence

    def get(self, evidence_id: str) -> StoredWorkOrderEvidence | None:
        with self._lock:
            return self._items.get(evidence_id)

    def list_by_work_order_id(self, work_order_id: str) -> list[StoredWorkOrderEvidence]:
        with self._lock:
            items = [item for item in self._items.values() if item.work_order_id == work_order_id]
        return sorted(items, key=lambda item: (item.created_at, item.evidence_id))

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredWorkOrderEvidence]:
        with self._lock:
            items = [item for item in self._items.values() if item.ticket_id == ticket_id]
        return sorted(items, key=lambda item: (item.created_at, item.evidence_id))

    def find_original_for_work_order(self, work_order_id: str) -> StoredWorkOrderEvidence | None:
        for item in self.list_by_work_order_id(work_order_id):
            if item.kind == "ORIGINAL_REPORT":
                return item
        return None

    def count_by_kind(self, work_order_id: str, kind: WorkOrderEvidenceKind) -> int:
        return sum(1 for item in self.list_by_work_order_id(work_order_id) if item.kind == kind)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


work_order_evidence_store = InMemoryWorkOrderEvidenceStore()
