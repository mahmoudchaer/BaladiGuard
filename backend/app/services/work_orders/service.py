"""Create, assign, start, complete, and cancel maintenance work orders (issue #247)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.core.staff_auth import StaffPrincipal, staff_can_access_ticket
from app.database.store_factory import get_ticket_store, get_work_order_store
from app.database.work_order_store import WorkOrderStore
from app.schemas.stored_ticket import StoredTicket
from app.schemas.ticket_response import UpdateTicketStatusRequest
from app.schemas.ticket_status import TicketStatus
from app.schemas.work_order import (
    CancelWorkOrderRequest,
    CompleteWorkOrderRequest,
    CreateWorkOrderRequest,
    StoredWorkOrder,
    WorkOrderListResponse,
    WorkOrderResponse,
    is_active_work_order_state,
)
from app.schemas.workforce import AssignWorkforceRequest
from app.services.routing import department_ids
from app.services.staff.bootstrap import BEIRUT_MUNICIPALITY_ID
from app.services.work_orders.reasons import (
    normalize_private_note,
    validate_work_order_cancel_reason,
)
from app.services.work_orders.transitions import (
    is_work_order_eligible_ticket_status,
    ticket_status_path,
    validate_work_order_transition,
)
from app.services.workforce.service import workforce_service


class WorkOrderError(Exception):
    def __init__(
        self, message: str, *, status_code: int = 400, code: str = "VALIDATION_ERROR"
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def generate_work_order_id() -> str:
    return f"wo_{uuid4().hex}"


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _default_summary(ticket: StoredTicket) -> str:
    text = (ticket.cleaned_description or ticket.description or "").strip()
    if not text:
        return f"Maintenance work for {ticket.ticket_number}"
    return text[:500]


class WorkOrderService:
    def __init__(self, store: WorkOrderStore | None = None) -> None:
        self._store = store

    def store(self) -> WorkOrderStore:
        return self._store or get_work_order_store()

    def create(
        self,
        ticket_id: str,
        payload: CreateWorkOrderRequest,
        *,
        principal: StaffPrincipal,
    ) -> WorkOrderResponse:
        ticket = self._require_ticket(ticket_id, principal)
        existing = self.store().find_active_for_ticket(ticket_id)
        if existing is not None:
            return WorkOrderResponse.from_work_order(
                existing, ticket_status=ticket.status, created=False
            )
        self._assert_ticket_can_receive_work(ticket)

        worker_id: str | None = None
        team_id: str | None = None
        if payload.worker_id or payload.team_id:
            worker_id, team_id = workforce_service.resolve_ticket_assignment(
                principal,
                ticket,
                AssignWorkforceRequest(workerId=payload.worker_id, teamId=payload.team_id),
            )

        created_at = _iso_now()
        state = "ASSIGNED" if worker_id or team_id else "QUEUED"
        work_order = StoredWorkOrder(
            workOrderId=generate_work_order_id(),
            ticketId=ticket.ticket_id,
            municipalityId=self._municipality_for(ticket, principal),
            departmentId=ticket.department_id or "",
            state=state,
            summary=payload.summary or _default_summary(ticket),
            assignedWorkerId=worker_id,
            assignedTeamId=team_id,
            createdAt=created_at,
            createdBy=principal.staff_id,
            updatedAt=created_at,
            updatedBy=principal.staff_id,
        )

        def _commit() -> StoredWorkOrder:
            raced = self.store().find_active_for_ticket(ticket_id)
            if raced is not None:
                return raced
            saved = self.store().save(work_order)
            patched = get_ticket_store().patch_fields(
                ticket_id,
                {
                    "active_work_order_id": saved.work_order_id,
                    "updated_at": created_at,
                    "updated_by": principal.staff_id,
                },
            )
            if patched is None:
                raise WorkOrderError(
                    "Ticket was not found.", status_code=404, code="TICKET_NOT_FOUND"
                )
            return saved

        saved = self.store().run_exclusive(_commit)
        created = saved.work_order_id == work_order.work_order_id
        if created:
            self._record_ticket_audit(
                ticket_id,
                action_type="WORK_ORDER_CREATE",
                principal=principal,
                summary=f"Work order {saved.work_order_id} created in {saved.state}.",
                previous_value=None,
                new_value=saved.work_order_id,
                created_at=created_at,
            )
            if worker_id or team_id:
                self._sync_ticket_workforce(
                    ticket_id,
                    AssignWorkforceRequest(workerId=worker_id, teamId=team_id),
                    principal=principal,
                )
            self._sync_ticket_status_toward(
                ticket_id,
                "ASSIGNED",
                principal=principal,
                note="Work order created.",
            )
        refreshed = get_ticket_store().get(ticket_id)
        return WorkOrderResponse.from_work_order(
            saved,
            ticket_status=refreshed.status if refreshed else ticket.status,
            created=created,
        )

    def list_for_ticket(
        self, ticket_id: str, *, principal: StaffPrincipal
    ) -> WorkOrderListResponse:
        ticket = self._require_ticket(ticket_id, principal)
        items = [
            WorkOrderResponse.from_work_order(item, ticket_status=ticket.status)
            for item in self.store().list_by_ticket_id(ticket_id)
        ]
        active = self.store().find_active_for_ticket(ticket_id)
        return WorkOrderListResponse(
            items=items,
            activeWorkOrderId=active.work_order_id if active else None,
        )

    def get(self, work_order_id: str, *, principal: StaffPrincipal) -> WorkOrderResponse:
        work_order, ticket = self._require_work_order(work_order_id, principal)
        return WorkOrderResponse.from_work_order(work_order, ticket_status=ticket.status)

    def assign(
        self,
        work_order_id: str,
        payload: AssignWorkforceRequest,
        *,
        principal: StaffPrincipal,
    ) -> WorkOrderResponse:
        work_order, ticket = self._require_work_order(work_order_id, principal)
        if not is_active_work_order_state(work_order.state):
            raise WorkOrderError("A completed or cancelled work order cannot be assigned.")
        worker_id, team_id = workforce_service.resolve_ticket_assignment(
            principal, ticket, payload
        )
        target_state: str = "QUEUED" if worker_id is None and team_id is None else "ASSIGNED"
        if work_order.state == "IN_PROGRESS" and target_state == "ASSIGNED":
            target_state = "IN_PROGRESS"
        if target_state != work_order.state:
            validate_work_order_transition(work_order.state, target_state)
        updated_at = _iso_now()
        updated = self.store().save(
            work_order.model_copy(
                update={
                    "state": target_state,
                    "assigned_worker_id": worker_id,
                    "assigned_team_id": team_id,
                    "updated_at": updated_at,
                    "updated_by": principal.staff_id,
                }
            )
        )
        self._record_ticket_audit(
            ticket.ticket_id,
            action_type="WORK_ORDER_ASSIGN",
            principal=principal,
            summary=(
                f"Work order {updated.work_order_id} assignment changed to "
                f"{worker_id or team_id or 'unassigned'}."
            ),
            previous_value=work_order.assigned_worker_id or work_order.assigned_team_id,
            new_value=worker_id or team_id,
            created_at=updated_at,
        )
        if worker_id or team_id or payload.clear:
            self._sync_ticket_workforce(ticket.ticket_id, payload, principal=principal)
        if target_state == "ASSIGNED":
            self._sync_ticket_status_toward(
                ticket.ticket_id,
                "ASSIGNED",
                principal=principal,
                note="Work order assigned.",
            )
        refreshed = get_ticket_store().get(ticket.ticket_id)
        return WorkOrderResponse.from_work_order(
            updated, ticket_status=refreshed.status if refreshed else ticket.status
        )

    def start(self, work_order_id: str, *, principal: StaffPrincipal) -> WorkOrderResponse:
        work_order, ticket = self._require_work_order(work_order_id, principal)
        if work_order.state == "QUEUED" and not (
            work_order.assigned_worker_id or work_order.assigned_team_id
        ):
            raise WorkOrderError("Assign a worker or team before starting this work order.")
        validate_work_order_transition(work_order.state, "IN_PROGRESS")
        updated_at = _iso_now()
        updated = self.store().save(
            work_order.model_copy(
                update={
                    "state": "IN_PROGRESS",
                    "started_at": work_order.started_at or updated_at,
                    "started_by": work_order.started_by or principal.staff_id,
                    "updated_at": updated_at,
                    "updated_by": principal.staff_id,
                }
            )
        )
        self._record_ticket_audit(
            ticket.ticket_id,
            action_type="WORK_ORDER_START",
            principal=principal,
            summary=f"Work order {updated.work_order_id} started.",
            previous_value=work_order.state,
            new_value="IN_PROGRESS",
            created_at=updated_at,
        )
        self._sync_ticket_status_toward(
            ticket.ticket_id,
            "IN_PROGRESS",
            principal=principal,
            note="Work order started.",
        )
        refreshed = get_ticket_store().get(ticket.ticket_id)
        return WorkOrderResponse.from_work_order(
            updated, ticket_status=refreshed.status if refreshed else ticket.status
        )

    def complete(
        self,
        work_order_id: str,
        payload: CompleteWorkOrderRequest,
        *,
        principal: StaffPrincipal,
    ) -> WorkOrderResponse:
        work_order, ticket = self._require_work_order(work_order_id, principal)
        validate_work_order_transition(work_order.state, "COMPLETED")
        self._assert_completion_allowed(work_order)
        updated_at = _iso_now()
        note = normalize_private_note(payload.note)
        updated = self.store().save(
            work_order.model_copy(
                update={
                    "state": "COMPLETED",
                    "completed_at": updated_at,
                    "completed_by": principal.staff_id,
                    "completion_note": note,
                    "updated_at": updated_at,
                    "updated_by": principal.staff_id,
                }
            )
        )
        get_ticket_store().patch_fields(
            ticket.ticket_id,
            {
                "active_work_order_id": None,
                "updated_at": updated_at,
                "updated_by": principal.staff_id,
            },
        )
        self._record_ticket_audit(
            ticket.ticket_id,
            action_type="WORK_ORDER_COMPLETE",
            principal=principal,
            summary=f"Work order {updated.work_order_id} completed.",
            previous_value=work_order.state,
            new_value="COMPLETED",
            created_at=updated_at,
        )
        refreshed = get_ticket_store().get(ticket.ticket_id)
        return WorkOrderResponse.from_work_order(
            updated, ticket_status=refreshed.status if refreshed else ticket.status
        )

    def cancel(
        self,
        work_order_id: str,
        payload: CancelWorkOrderRequest,
        *,
        principal: StaffPrincipal,
    ) -> WorkOrderResponse:
        work_order, ticket = self._require_work_order(work_order_id, principal)
        validate_work_order_transition(work_order.state, "CANCELLED")
        reason_code = validate_work_order_cancel_reason(payload.reason_code)
        note = normalize_private_note(payload.note)
        updated_at = _iso_now()
        updated = self.store().save(
            work_order.model_copy(
                update={
                    "state": "CANCELLED",
                    "cancelled_at": updated_at,
                    "cancelled_by": principal.staff_id,
                    "cancel_reason_code": reason_code,
                    "cancel_note": note,
                    "updated_at": updated_at,
                    "updated_by": principal.staff_id,
                }
            )
        )
        get_ticket_store().patch_fields(
            ticket.ticket_id,
            {
                "active_work_order_id": None,
                "updated_at": updated_at,
                "updated_by": principal.staff_id,
            },
        )
        self._record_ticket_audit(
            ticket.ticket_id,
            action_type="WORK_ORDER_CANCEL",
            principal=principal,
            summary=f"Work order {updated.work_order_id} cancelled ({reason_code}).",
            previous_value=work_order.state,
            new_value=reason_code,
            created_at=updated_at,
        )
        refreshed = get_ticket_store().get(ticket.ticket_id)
        return WorkOrderResponse.from_work_order(
            updated, ticket_status=refreshed.status if refreshed else ticket.status
        )

    def _assert_completion_allowed(self, work_order: StoredWorkOrder) -> None:
        """#248 will require after-image evidence here. Completion never resolves the ticket."""
        del work_order

    def _assert_ticket_can_receive_work(self, ticket: StoredTicket) -> None:
        if not is_work_order_eligible_ticket_status(ticket.status):
            raise WorkOrderError(
                "A work order can only be created for an accepted ticket "
                "(under review, assigned, or in progress)."
            )
        if ticket.department_id not in department_ids():
            raise WorkOrderError(
                "A responsible department must be assigned before creating a work order."
            )
        if ticket_status_path(ticket.status, "ASSIGNED") is None and ticket.status != "ASSIGNED":
            if ticket.status != "IN_PROGRESS":
                raise WorkOrderError(
                    "Creating a work order would require a ticket status change "
                    "that is not allowed."
                )

    def _municipality_for(self, ticket: StoredTicket, principal: StaffPrincipal) -> str:
        if ticket.municipality_id:
            return ticket.municipality_id
        if principal.municipality_id:
            return principal.municipality_id
        return BEIRUT_MUNICIPALITY_ID

    def _require_ticket(self, ticket_id: str, principal: StaffPrincipal) -> StoredTicket:
        ticket = get_ticket_store().get(ticket_id)
        if ticket is None or not staff_can_access_ticket(principal, ticket):
            raise WorkOrderError("Ticket was not found.", status_code=404, code="TICKET_NOT_FOUND")
        return ticket

    def _require_work_order(
        self, work_order_id: str, principal: StaffPrincipal
    ) -> tuple[StoredWorkOrder, StoredTicket]:
        work_order = self.store().get(work_order_id)
        if work_order is None:
            raise WorkOrderError(
                "Work order was not found.", status_code=404, code="WORK_ORDER_NOT_FOUND"
            )
        ticket = self._require_ticket(work_order.ticket_id, principal)
        return work_order, ticket

    def _sync_ticket_status_toward(
        self,
        ticket_id: str,
        target_status: TicketStatus,
        *,
        principal: StaffPrincipal,
        note: str,
    ) -> None:
        from app.services.complaints.status_workflow import InvalidStatusTransitionError
        from app.services.complaints.ticket_service import ticket_service

        ticket = get_ticket_store().get(ticket_id)
        if ticket is None or ticket.status == target_status:
            return
        rank = {
            "SUBMITTED": 0,
            "UNDER_REVIEW": 1,
            "ASSIGNED": 2,
            "IN_PROGRESS": 3,
            "RESOLVED": 4,
            "CLOSED": 5,
        }
        if rank.get(ticket.status, 0) >= rank.get(target_status, 0):
            return
        path = ticket_status_path(ticket.status, target_status)
        if path is None:
            return
        try:
            for next_status in path:
                current = get_ticket_store().get(ticket_id)
                if current is None or current.status == next_status:
                    continue
                ticket_service.update_ticket_status(
                    ticket_id,
                    UpdateTicketStatusRequest(status=next_status, note=note),
                    staff_principal=principal,
                )
        except InvalidStatusTransitionError as exc:
            raise WorkOrderError(str(exc), code="INVALID_STATUS_TRANSITION") from exc

    def _sync_ticket_workforce(
        self,
        ticket_id: str,
        payload: AssignWorkforceRequest,
        *,
        principal: StaffPrincipal,
    ) -> None:
        from app.services.complaints.ticket_service import TicketNotFoundError, ticket_service

        try:
            ticket_service.assign_ticket_workforce(
                ticket_id, payload, staff_principal=principal
            )
        except TicketNotFoundError:
            return

    def _record_ticket_audit(
        self,
        ticket_id: str,
        *,
        action_type: str,
        principal: StaffPrincipal,
        summary: str,
        previous_value: str | None,
        new_value: str | None,
        created_at: str,
    ) -> None:
        from app.services.complaints.ticket_service import ticket_service

        ticket_service._record_audit_history(  # noqa: SLF001
            ticket_id=ticket_id,
            action_type=action_type,  # type: ignore[arg-type]
            actor_id=principal.staff_id,
            actor_role=principal.role,
            summary=summary,
            previous_value=previous_value,
            new_value=new_value,
            created_at=created_at,
        )


work_order_service = WorkOrderService()
