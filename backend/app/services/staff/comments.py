"""Private staff comments and normalized internal activity timeline (#246)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.core.staff_auth import StaffPrincipal, principal_from_user, staff_can_access_ticket
from app.database.store_factory import (
    get_audit_history_store,
    get_staff_comment_store,
    get_staff_store,
    get_status_history_store,
    get_ticket_store,
)
from app.schemas.staff_comment import (
    ActivityEvent,
    ActivityTimelineResponse,
    CreateStaffCommentRequest,
    StaffCommentResponse,
    StoredStaffComment,
)
from app.schemas.stored_audit_history import StoredAuditHistory


class StaffCommentError(Exception):
    def __init__(
        self, message: str, *, code: str = "VALIDATION_ERROR", status_code: int = 400
    ) -> None:
        self.message, self.code, self.status_code = message, code, status_code


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _comment_response(comment: StoredStaffComment) -> StaffCommentResponse:
    author = get_staff_store().get(comment.author_staff_id)
    return StaffCommentResponse(
        commentId=comment.comment_id,
        ticketId=comment.ticket_id,
        authorStaffId=comment.author_staff_id,
        authorDisplayName=author.name if author else "Staff member",
        text=comment.text,
        mentionedStaffIds=comment.mentioned_staff_ids,
        createdAt=comment.created_at,
    )


def _ticket_for(principal: StaffPrincipal, ticket_id: str):
    ticket = get_ticket_store().get(ticket_id)
    if ticket is None or not staff_can_access_ticket(principal, ticket):
        raise StaffCommentError("Ticket was not found.", code="TICKET_NOT_FOUND", status_code=404)
    return ticket


class StaffCommentService:
    def create(
        self, ticket_id: str, payload: CreateStaffCommentRequest, *, principal: StaffPrincipal
    ) -> StaffCommentResponse:
        ticket = _ticket_for(principal, ticket_id)
        mentioned = list(dict.fromkeys(payload.mentioned_staff_ids))
        if len(mentioned) != len(payload.mentioned_staff_ids):
            raise StaffCommentError("Mentioned staff IDs must be unique.")
        for staff_id in mentioned:
            user = get_staff_store().get(staff_id)
            if (
                user is None
                or not user.active
                or not staff_can_access_ticket(principal_from_user(user), ticket)
            ):
                raise StaffCommentError(
                    "A mentioned staff account is unknown, inactive, or out of scope."
                )
        comment = StoredStaffComment(
            commentId=f"cmt_{uuid4().hex}",
            ticketId=ticket_id,
            authorStaffId=principal.staff_id,
            text=payload.text,
            mentionedStaffIds=mentioned,
            createdAt=_now(),
        )
        get_staff_comment_store().append(comment)
        get_audit_history_store().append(
            StoredAuditHistory(
                auditId=f"audit_{uuid4().hex}",
                ticketId=ticket_id,
                actionType="STAFF_COMMENT",
                actorId=principal.staff_id,
                actorRole=principal.role,
                summary="Staff comment added.",
                createdAt=comment.created_at,
            )
        )
        return _comment_response(comment)

    def list(self, ticket_id: str, *, principal: StaffPrincipal) -> list[StaffCommentResponse]:
        _ticket_for(principal, ticket_id)
        return [
            _comment_response(comment)
            for comment in get_staff_comment_store().list_by_ticket_id(ticket_id)
        ]

    def timeline(
        self, ticket_id: str, *, principal: StaffPrincipal, limit: int, cursor: str | None
    ) -> ActivityTimelineResponse:
        _ticket_for(principal, ticket_id)
        events: list[ActivityEvent] = []
        for entry in get_status_history_store().list_by_ticket_id(ticket_id):
            events.append(
                ActivityEvent(
                    eventId=f"status:{entry.history_id}",
                    eventType="STATUS_CHANGED",
                    occurredAt=entry.created_at,
                    actorDisplayName=entry.updated_by,
                    details={"status": entry.new_status},
                    sourceReference=f"status-history:{entry.history_id}",
                )
            )
        for entry in get_audit_history_store().list_by_ticket_id(ticket_id):
            if entry.action_type in {"STAFF_COMMENT", "STATUS_CHANGE"}:
                continue
            events.append(
                ActivityEvent(
                    eventId=f"audit:{entry.audit_id}",
                    eventType=entry.action_type,
                    occurredAt=entry.created_at,
                    actorDisplayName=entry.actor_id,
                    details={"summary": entry.summary},
                    sourceReference=f"audit:{entry.audit_id}",
                )
            )
        for comment in get_staff_comment_store().list_by_ticket_id(ticket_id):
            events.append(
                ActivityEvent(
                    eventId=f"comment:{comment.comment_id}",
                    eventType="STAFF_COMMENT",
                    occurredAt=comment.created_at,
                    actorDisplayName=_comment_response(comment).author_display_name,
                    details={"commentId": comment.comment_id},
                    sourceReference=f"comment:{comment.comment_id}",
                )
            )
        events.sort(key=lambda event: (event.occurred_at, event.source_reference, event.event_id))
        start = int(cursor or "0")
        page = events[start : start + limit]
        next_cursor = str(start + limit) if start + limit < len(events) else None
        return ActivityTimelineResponse(events=page, nextCursor=next_cursor)


staff_comment_service = StaffCommentService()
