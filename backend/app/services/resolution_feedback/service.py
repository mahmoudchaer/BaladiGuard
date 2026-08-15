"""Citizen resolution verification and municipal review (issues #248 / #261)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.staff_auth import StaffPrincipal, staff_can_access_ticket
from app.database.store_factory import (
    get_resolution_review_store,
    get_ticket_store,
)
from app.database.ticket_store import TicketStore
from app.schemas.resolution_feedback import (
    CitizenResolutionFeedbackResponse,
    ResolutionReviewQueueItem,
    ResolutionReviewQueueResponse,
    ReviewResolutionFeedbackRequest,
    StaffResolutionFeedbackResponse,
    StoredResolutionReview,
    SubmitResolutionFeedbackRequest,
)
from app.schemas.stored_ticket import StoredTicket
from app.services.notifications.recipients import ticket_notification_recipient
from app.services.notifications.service import emit_ticket_notification


class ResolutionFeedbackError(Exception):
    def __init__(
        self, message: str, *, status_code: int = 400, code: str = "VALIDATION_ERROR"
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _normalize_note(note: str | None) -> str | None:
    if note is None:
        return None
    trimmed = note.strip()
    return trimmed or None


def needs_resolution_review(ticket: StoredTicket) -> bool:
    return (
        ticket.resolution_feedback_status == "STILL_UNRESOLVED"
        and ticket.resolution_feedback_review_status == "PENDING"
    )


def assert_closure_allowed(ticket: StoredTicket) -> None:
    if needs_resolution_review(ticket):
        raise ResolutionFeedbackError(
            "Unresolved citizen feedback must be reviewed before this ticket can be closed.",
            code="RESOLUTION_FEEDBACK_REVIEW_REQUIRED",
        )


class ResolutionFeedbackService:
    def __init__(self, tickets: TicketStore | None = None) -> None:
        self._tickets = tickets

    def tickets(self) -> TicketStore:
        return self._tickets or get_ticket_store()

    def citizen_view(
        self, tracking_code: str, *, owner_user_id: str
    ) -> CitizenResolutionFeedbackResponse:
        ticket = self._require_owned_ticket(tracking_code, owner_user_id)
        return CitizenResolutionFeedbackResponse(
            trackingCode=ticket.tracking_code,
            ticketStatus=ticket.status,
            canSubmit=self._can_submit(ticket, owner_user_id),
            status=ticket.resolution_feedback_status,
            submittedAt=ticket.resolution_feedback_submitted_at,
        )

    def submit_citizen_feedback(
        self,
        tracking_code: str,
        payload: SubmitResolutionFeedbackRequest,
        *,
        owner_user_id: str,
    ) -> CitizenResolutionFeedbackResponse:
        ticket = self._require_owned_ticket(tracking_code, owner_user_id)
        already_open = ticket.resolution_feedback_status is None
        if not self._can_submit(ticket, owner_user_id) and already_open:
            raise ResolutionFeedbackError(
                "Resolution feedback can only be submitted for an owned resolved ticket.",
                code="FEEDBACK_NOT_ELIGIBLE",
            )
        if ticket.status != "RESOLVED" or ticket.owner_user_id != owner_user_id:
            raise ResolutionFeedbackError(
                "Resolution feedback can only be submitted for an owned resolved ticket.",
                code="FEEDBACK_NOT_ELIGIBLE",
            )

        note = _normalize_note(payload.note)
        existing_status = ticket.resolution_feedback_status
        existing_note = _normalize_note(ticket.resolution_feedback_note)
        if existing_status is not None:
            if existing_status == payload.status and existing_note == note:
                return self.citizen_view(tracking_code, owner_user_id=owner_user_id)
            raise ResolutionFeedbackError(
                "Resolution feedback was already submitted for this ticket.",
                status_code=409,
                code="RESOLUTION_FEEDBACK_ALREADY_SUBMITTED",
            )

        submitted_at = _iso_now()
        review_status = "PENDING" if payload.status == "STILL_UNRESOLVED" else None
        fields = {
            "resolution_feedback_status": payload.status,
            "resolution_feedback_note": note,
            "resolution_feedback_submitted_at": submitted_at,
            "resolution_feedback_review_status": review_status,
            "resolution_feedback_reviewed_at": None,
            "resolution_feedback_reviewed_by": None,
            "resolution_feedback_review_action": None,
            "updated_at": submitted_at,
        }
        review_item = None
        if payload.status == "STILL_UNRESOLVED":
            review_item = StoredResolutionReview(
                reviewId=f"rr_{ticket.ticket_id}",
                ticketId=ticket.ticket_id,
                trackingCode=ticket.tracking_code,
                municipalityId=ticket.municipality_id,
                departmentId=ticket.department_id,
                ticketStatus="RESOLVED",
                feedbackStatus="STILL_UNRESOLVED",
                submittedAt=submitted_at,
                reviewStatus="PENDING",
            )
        try:
            updated = self.tickets().commit_resolution_feedback(
                ticket.ticket_id,
                fields,
                expected_updated_at=ticket.updated_at,
                expected_values={
                    "status": "RESOLVED",
                    "owner_user_id": owner_user_id,
                    "resolution_feedback_status": None,
                },
                review_item=review_item,
                delete_review=payload.status != "STILL_UNRESOLVED",
            )
        except Exception as exc:
            raise ResolutionFeedbackError(
                "Resolution feedback could not be recorded.",
                status_code=502,
                code="RESOLUTION_FEEDBACK_COMMIT_FAILED",
            ) from exc
        if updated is None:
            return self._submit_after_conflict(
                tracking_code, payload, owner_user_id=owner_user_id, note=note
            )

        self._record_audit(
            updated.ticket_id,
            action_type="RESOLUTION_FEEDBACK_SUBMIT",
            actor_id=None,
            actor_role=None,
            summary=(
                "Citizen resolution feedback submitted "
                f"({payload.status.replace('_', ' ').lower()})."
            ),
            previous_value=None,
            new_value=payload.status,
            created_at=submitted_at,
        )
        emit_ticket_notification(
            event="resolution_feedback_received",
            ticket_id=updated.ticket_id,
            status=payload.status,
            tracking_code=updated.tracking_code,
            ticket_number=updated.ticket_number,
            recipient=ticket_notification_recipient(updated),
        )
        return self.citizen_view(tracking_code, owner_user_id=owner_user_id)

    def staff_view(
        self, ticket_id: str, *, principal: StaffPrincipal
    ) -> StaffResolutionFeedbackResponse:
        ticket = self._require_staff_ticket(ticket_id, principal)
        return self._staff_response(ticket)

    def review(
        self,
        ticket_id: str,
        payload: ReviewResolutionFeedbackRequest,
        *,
        principal: StaffPrincipal,
    ) -> StaffResolutionFeedbackResponse:
        ticket = self._require_staff_ticket(ticket_id, principal)
        if ticket.resolution_feedback_status != "STILL_UNRESOLVED":
            raise ResolutionFeedbackError(
                "There is no unresolved citizen feedback to review.",
                code="FEEDBACK_REVIEW_NOT_ELIGIBLE",
            )
        existing_action = ticket.resolution_feedback_review_action
        if (
            ticket.resolution_feedback_review_status == "REVIEWED"
            and existing_action == payload.action
        ):
            return self._staff_response(ticket)
        if ticket.resolution_feedback_review_status == "REVIEWED":
            raise ResolutionFeedbackError(
                "This unresolved feedback was already reviewed.",
                status_code=409,
                code="RESOLUTION_FEEDBACK_ALREADY_REVIEWED",
            )

        reviewed_at = _iso_now()
        fields: dict[str, object] = {
            "resolution_feedback_review_status": "REVIEWED",
            "resolution_feedback_reviewed_at": reviewed_at,
            "resolution_feedback_reviewed_by": principal.staff_id,
            "resolution_feedback_review_action": payload.action,
            "updated_at": reviewed_at,
            "updated_by": principal.staff_id,
        }
        if payload.action == "RETURN_IN_PROGRESS":
            if ticket.status != "RESOLVED":
                raise ResolutionFeedbackError(
                    "There is no unresolved citizen feedback to review.",
                    code="FEEDBACK_REVIEW_NOT_ELIGIBLE",
                )
            fields["status"] = "IN_PROGRESS"
        queued = get_resolution_review_store().get_by_ticket_id(ticket.ticket_id)
        if queued is None:
            queued = StoredResolutionReview(
                reviewId=f"rr_{ticket.ticket_id}",
                ticketId=ticket.ticket_id,
                trackingCode=ticket.tracking_code,
                municipalityId=ticket.municipality_id,
                departmentId=ticket.department_id,
                ticketStatus=ticket.status,
                feedbackStatus="STILL_UNRESOLVED",
                submittedAt=ticket.resolution_feedback_submitted_at or reviewed_at,
                reviewStatus="PENDING",
            )
        reviewed_queue_item = queued.model_copy(
            update={
                "ticket_status": fields.get("status", ticket.status),
                "review_status": "REVIEWED",
            }
        )
        try:
            updated = self.tickets().commit_resolution_feedback(
                ticket.ticket_id,
                fields,
                expected_updated_at=ticket.updated_at,
                expected_values={
                    "resolution_feedback_status": "STILL_UNRESOLVED",
                    "resolution_feedback_review_status": "PENDING",
                    "status": ticket.status,
                },
                review_item=reviewed_queue_item,
            )
        except Exception as exc:
            raise ResolutionFeedbackError(
                "The review could not be committed.",
                status_code=502,
                code="RESOLUTION_FEEDBACK_REVIEW_COMMIT_FAILED",
            ) from exc
        if updated is None:
            return self._review_after_conflict(ticket_id, payload, principal=principal)

        self._record_audit(
            updated.ticket_id,
            action_type="RESOLUTION_FEEDBACK_REVIEW",
            actor_id=principal.staff_id,
            actor_role=principal.role,
            summary=(
                "Staff reviewed unresolved citizen feedback "
                f"({payload.action.replace('_', ' ').lower()})."
            ),
            previous_value="PENDING",
            new_value=payload.action,
            created_at=reviewed_at,
        )

        if payload.action == "RETURN_IN_PROGRESS" and updated.status == "IN_PROGRESS":
            from app.services.complaints.ticket_service import ticket_service

            ticket_service._record_status_history(  # noqa: SLF001
                ticket_id=updated.ticket_id,
                previous_status="RESOLVED",
                new_status="IN_PROGRESS",
                updated_by=principal.staff_id,
                note=_normalize_note(payload.note) or "Returned after citizen feedback review.",
                created_at=reviewed_at,
            )

        return self._staff_response(updated)

    def list_review_queue(self, *, principal: StaffPrincipal) -> ResolutionReviewQueueResponse:
        municipality_id = None if principal.role == "administrator" else principal.municipality_id
        items = []
        for review in get_resolution_review_store().list_pending(municipality_id=municipality_id):
            ticket = self.tickets().get(review.ticket_id)
            if ticket is None or not staff_can_access_ticket(principal, ticket):
                continue
            if not needs_resolution_review(ticket):
                continue
            items.append(
                ResolutionReviewQueueItem(
                    ticketId=ticket.ticket_id,
                    trackingCode=ticket.tracking_code,
                    municipalityId=ticket.municipality_id,
                    departmentId=ticket.department_id,
                    ticketStatus=ticket.status,
                    feedbackStatus="STILL_UNRESOLVED",
                    submittedAt=ticket.resolution_feedback_submitted_at or review.submitted_at,
                    reviewStatus="PENDING",
                )
            )
        return ResolutionReviewQueueResponse(items=items)

    def _submit_after_conflict(
        self,
        tracking_code: str,
        payload: SubmitResolutionFeedbackRequest,
        *,
        owner_user_id: str,
        note: str | None,
    ) -> CitizenResolutionFeedbackResponse:
        ticket = self._require_owned_ticket(tracking_code, owner_user_id)
        existing_status = ticket.resolution_feedback_status
        existing_note = _normalize_note(ticket.resolution_feedback_note)
        if existing_status is not None:
            if existing_status == payload.status and existing_note == note:
                return self.citizen_view(tracking_code, owner_user_id=owner_user_id)
            raise ResolutionFeedbackError(
                "Resolution feedback was already submitted for this ticket.",
                status_code=409,
                code="RESOLUTION_FEEDBACK_ALREADY_SUBMITTED",
            )
        if ticket.status != "RESOLVED" or ticket.owner_user_id != owner_user_id:
            raise ResolutionFeedbackError(
                "Resolution feedback can only be submitted for an owned resolved ticket.",
                code="FEEDBACK_NOT_ELIGIBLE",
            )
        raise ResolutionFeedbackError(
            "Ticket was updated by another request. Retry the feedback submission.",
            status_code=409,
            code="RESOLUTION_FEEDBACK_CONFLICT",
        )

    def _review_after_conflict(
        self,
        ticket_id: str,
        payload: ReviewResolutionFeedbackRequest,
        *,
        principal: StaffPrincipal,
    ) -> StaffResolutionFeedbackResponse:
        ticket = self._require_staff_ticket(ticket_id, principal)
        if (
            ticket.resolution_feedback_review_status == "REVIEWED"
            and ticket.resolution_feedback_review_action == payload.action
        ):
            return self._staff_response(ticket)
        if ticket.resolution_feedback_review_status == "REVIEWED":
            raise ResolutionFeedbackError(
                "This unresolved feedback was already reviewed.",
                status_code=409,
                code="RESOLUTION_FEEDBACK_ALREADY_REVIEWED",
            )
        raise ResolutionFeedbackError(
            "The review could not be applied because the ticket changed.",
            status_code=409,
            code="FEEDBACK_REVIEW_CONFLICT",
        )

    def _can_submit(self, ticket: StoredTicket, owner_user_id: str) -> bool:
        return (
            ticket.status == "RESOLVED"
            and ticket.owner_user_id == owner_user_id
            and ticket.resolution_feedback_status is None
        )

    def _require_owned_ticket(self, tracking_code: str, owner_user_id: str) -> StoredTicket:
        ticket = self.tickets().get_by_tracking_code(tracking_code)
        if ticket is None or ticket.owner_user_id != owner_user_id:
            raise ResolutionFeedbackError(
                "Ticket was not found.", status_code=404, code="TICKET_NOT_FOUND"
            )
        return ticket

    def _require_staff_ticket(self, ticket_id: str, principal: StaffPrincipal) -> StoredTicket:
        ticket = self.tickets().get(ticket_id)
        if ticket is None or not staff_can_access_ticket(principal, ticket):
            raise ResolutionFeedbackError(
                "Ticket was not found.", status_code=404, code="TICKET_NOT_FOUND"
            )
        return ticket

    def _staff_response(self, ticket: StoredTicket) -> StaffResolutionFeedbackResponse:
        return StaffResolutionFeedbackResponse(
            ticketId=ticket.ticket_id,
            trackingCode=ticket.tracking_code,
            ticketStatus=ticket.status,
            status=ticket.resolution_feedback_status,
            note=ticket.resolution_feedback_note,
            submittedAt=ticket.resolution_feedback_submitted_at,
            reviewStatus=ticket.resolution_feedback_review_status,
            reviewedAt=ticket.resolution_feedback_reviewed_at,
            reviewedBy=ticket.resolution_feedback_reviewed_by,
            reviewAction=ticket.resolution_feedback_review_action,
            needsReview=needs_resolution_review(ticket),
        )

    def _record_audit(
        self,
        ticket_id: str,
        *,
        action_type: str,
        actor_id: str | None,
        actor_role: str | None,
        summary: str,
        previous_value: str | None,
        new_value: str | None,
        created_at: str,
    ) -> None:
        from app.services.complaints.ticket_service import ticket_service

        ticket_service._record_audit_history(  # noqa: SLF001
            ticket_id=ticket_id,
            action_type=action_type,  # type: ignore[arg-type]
            actor_id=actor_id,
            actor_role=actor_role,  # type: ignore[arg-type]
            summary=summary,
            previous_value=previous_value,
            new_value=new_value,
            created_at=created_at,
        )


resolution_feedback_service = ResolutionFeedbackService()
