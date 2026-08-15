"""Private staff comments and normalized internal activity timeline (#246)."""

from __future__ import annotations

import base64
import binascii
import json
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


def _actor_display_name(actor_id: str | None) -> str | None:
    """Project actors to safe staff display names, never raw personnel IDs."""
    if actor_id is None:
        return "Citizen"
    staff = get_staff_store().get(actor_id)
    return staff.name if staff and staff.active else "Staff member"


_SAFE_AUDIT_SUMMARIES = {
    "WORKFORCE_ASSIGN": "Workforce assignment changed.",
    "WORK_ORDER_CREATE": "Work order created.",
    "WORK_ORDER_ASSIGN": "Work order assignment changed.",
    "WORK_ORDER_START": "Work order started.",
    "WORK_ORDER_COMPLETE": "Work order completed.",
    "WORK_ORDER_CANCEL": "Work order cancelled.",
    "WORK_ORDER_EVIDENCE_ADD": "Maintenance evidence added.",
    "RESOLUTION_FEEDBACK_SUBMIT": "Citizen resolution feedback submitted.",
    "RESOLUTION_FEEDBACK_REVIEW": "Citizen resolution feedback reviewed.",
}


def _encode_cursor(event: ActivityEvent) -> str:
    value = json.dumps(
        [event.occurred_at, event.source_reference, event.event_id], separators=(",", ":")
    ).encode()
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode_cursor(cursor: str | None) -> tuple[str, str, str] | None:
    if not cursor:
        return None
    # Accept the original numeric cursor for clients deployed before #271.
    if cursor.isdigit():
        return ("", "", f"__offset__:{cursor}")
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded).decode())
        if (
            not isinstance(value, list)
            or len(value) != 3
            or not all(isinstance(item, str) for item in value)
        ):
            raise ValueError
        return value[0], value[1], value[2]
    except (
        ValueError,
        TypeError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        binascii.Error,
    ):
        raise ValueError("invalid activity cursor") from None


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
                    actorDisplayName=_actor_display_name(entry.updated_by),
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
                    actorDisplayName=_actor_display_name(entry.actor_id),
                    details={
                        "summary": _SAFE_AUDIT_SUMMARIES.get(entry.action_type, entry.summary),
                        **(
                            {"previousValue": entry.previous_value}
                            if entry.previous_value
                            and entry.action_type.startswith("RESOLUTION_FEEDBACK_")
                            else {}
                        ),
                        **(
                            {"newValue": entry.new_value}
                            if entry.new_value
                            and entry.action_type.startswith("RESOLUTION_FEEDBACK_")
                            else {}
                        ),
                    },
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
        # Audit rows are the authoritative idempotency boundary: a replayed domain
        # operation or an overlapping audit read must never render twice.
        unique: dict[str, ActivityEvent] = {}
        for event in events:
            unique.setdefault(event.source_reference, event)
        events = sorted(
            unique.values(),
            key=lambda event: (event.occurred_at, event.source_reference, event.event_id),
        )
        decoded = _decode_cursor(cursor)
        if decoded and decoded[2].startswith("__offset__:"):
            start = int(decoded[2].split(":", 1)[1])
            page = events[start : start + limit]
        else:
            page = events
            if decoded:
                page = [
                    event
                    for event in events
                    if (event.occurred_at, event.source_reference, event.event_id) > decoded
                ]
            page = page[:limit]
        next_cursor = _encode_cursor(page[-1]) if len(page) == limit and page else None
        return ActivityTimelineResponse(events=page, nextCursor=next_cursor)


staff_comment_service = StaffCommentService()
