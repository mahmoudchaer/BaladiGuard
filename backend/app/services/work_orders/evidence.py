"""Attach and list private maintenance evidence (issue #248)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import UploadFile

from app.core.staff_auth import StaffPrincipal
from app.database.store_factory import get_work_order_evidence_store
from app.database.work_order_evidence_store import WorkOrderEvidenceStore
from app.schemas.work_order import StoredWorkOrder, is_active_work_order_state
from app.schemas.work_order_evidence import (
    UPLOADABLE_EVIDENCE_KINDS,
    StoredWorkOrderEvidence,
    WorkOrderEvidenceResponse,
)
from app.services.complaints.ticket_read_mapper import build_image_url
from app.services.uploads.photo_upload_service import (
    InvalidUploadError,
    S3UploadError,
    photo_upload_service,
)
from app.services.work_orders.service import WorkOrderError, work_order_service


def generate_evidence_id() -> str:
    return f"ev_{uuid4().hex}"


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class WorkOrderEvidenceService:
    def __init__(self, store: WorkOrderEvidenceStore | None = None) -> None:
        self._store = store

    def store(self) -> WorkOrderEvidenceStore:
        return self._store or get_work_order_evidence_store()

    def list_for_work_order(self, work_order_id: str) -> list[WorkOrderEvidenceResponse]:
        return [
            WorkOrderEvidenceResponse.from_stored(
                item, photo_url=build_image_url(item.object_key)
            )
            for item in self.store().list_by_work_order_id(work_order_id)
        ]

    def after_image_count(self, work_order_id: str) -> int:
        return self.store().count_by_kind(work_order_id, "AFTER")

    def associate_original_report(
        self,
        work_order: StoredWorkOrder,
        *,
        object_key: str,
        uploaded_by: str,
    ) -> StoredWorkOrderEvidence | None:
        key = (object_key or "").strip()
        if not key:
            return None
        existing = self.store().find_original_for_work_order(work_order.work_order_id)
        if existing is not None:
            return existing
        created_at = _iso_now()
        evidence = StoredWorkOrderEvidence(
            evidenceId=generate_evidence_id(),
            ticketId=work_order.ticket_id,
            workOrderId=work_order.work_order_id,
            kind="ORIGINAL_REPORT",
            objectKey=key,
            contentType="image/jpeg",
            uploadedBy=uploaded_by,
            createdAt=created_at,
            source="TICKET_ORIGINAL",
        )
        return self.store().save(evidence)

    async def attach_upload(
        self,
        work_order_id: str,
        *,
        kind: str,
        file: UploadFile | None,
        principal: StaffPrincipal,
    ) -> WorkOrderEvidenceResponse:
        if kind not in UPLOADABLE_EVIDENCE_KINDS:
            raise WorkOrderError(
                "Evidence kind must be BEFORE or AFTER.",
                code="INVALID_EVIDENCE_KIND",
            )
        if file is None:
            raise WorkOrderError(
                "An image file is required.",
                status_code=400,
                code="MISSING_FILE",
            )
        work_order, _ticket = work_order_service._require_work_order(  # noqa: SLF001
            work_order_id, principal
        )
        if not is_active_work_order_state(work_order.state):
            raise WorkOrderError(
                "Evidence can only be attached to an active work order.",
                code="WORK_ORDER_NOT_ACTIVE",
            )
        try:
            object_key, content_type = await photo_upload_service.upload_work_order_evidence(
                file,
                ticket_id=work_order.ticket_id,
                work_order_id=work_order.work_order_id,
                kind=kind,
            )
        except InvalidUploadError as exc:
            raise WorkOrderError(exc.message, code=exc.code) from exc
        except S3UploadError as exc:
            raise WorkOrderError(
                "Failed to upload image to storage.",
                status_code=502,
                code="S3_UPLOAD_FAILED",
            ) from exc

        created_at = _iso_now()
        evidence = StoredWorkOrderEvidence(
            evidenceId=generate_evidence_id(),
            ticketId=work_order.ticket_id,
            workOrderId=work_order.work_order_id,
            kind=kind,  # type: ignore[arg-type]
            objectKey=object_key,
            contentType=content_type,
            uploadedBy=principal.staff_id,
            createdAt=created_at,
            source="UPLOAD",
        )
        saved = self.store().save(evidence)
        work_order_service._record_ticket_audit(  # noqa: SLF001
            work_order.ticket_id,
            action_type="WORK_ORDER_EVIDENCE_ADD",
            principal=principal,
            summary=(
                f"{kind.replace('_', ' ').title()} image attached to work order "
                f"{work_order.work_order_id}."
            ),
            previous_value=None,
            new_value=kind,
            created_at=created_at,
        )
        return WorkOrderEvidenceResponse.from_stored(
            saved, photo_url=build_image_url(saved.object_key)
        )


work_order_evidence_service = WorkOrderEvidenceService()
