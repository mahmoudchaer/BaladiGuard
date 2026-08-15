"""Work-order evidence store protocol (issue #248)."""

from __future__ import annotations

from typing import Protocol

from app.schemas.work_order_evidence import StoredWorkOrderEvidence, WorkOrderEvidenceKind


class WorkOrderEvidenceStore(Protocol):
    def save(self, evidence: StoredWorkOrderEvidence) -> StoredWorkOrderEvidence: ...

    def get(self, evidence_id: str) -> StoredWorkOrderEvidence | None: ...

    def list_by_work_order_id(self, work_order_id: str) -> list[StoredWorkOrderEvidence]: ...

    def list_by_ticket_id(self, ticket_id: str) -> list[StoredWorkOrderEvidence]: ...

    def find_original_for_work_order(
        self, work_order_id: str
    ) -> StoredWorkOrderEvidence | None: ...

    def count_by_kind(self, work_order_id: str, kind: WorkOrderEvidenceKind) -> int: ...

    def clear(self) -> None: ...
