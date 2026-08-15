"""Structured ticket and work-order outcome reasons (issues #247 / #251)."""

from __future__ import annotations

from typing import Literal

from app.schemas.ticket_status import TicketStatus

OutcomeKind = Literal["resolution", "rejection", "closure"]
PRIVATE_NOTE_MAX_LENGTH = 500

RESOLUTION_REASON_CODES: dict[str, str] = {
    "WORK_COMPLETED": "The reported issue has been resolved.",
    "TEMPORARY_FIX": "A temporary repair has been applied.",
    "NO_WORK_REQUIRED": "Inspection found no municipal work was required.",
    "REFERRED_EXTERNAL": "The report was referred to another authority.",
    "DUPLICATE_RESOLVED": "This report was resolved as a duplicate of an existing case.",
}

REJECTION_REASON_CODES: dict[str, str] = {
    "OUT_OF_SCOPE": "This report is outside municipal responsibility.",
    "INSUFFICIENT_INFORMATION": "There was not enough information to act on this report.",
    "DUPLICATE": "This report matches an existing case.",
    "INVALID_REPORT": "This report could not be accepted as a municipal issue.",
    "CITIZEN_WITHDRAWN": "The report was withdrawn.",
    "SPAM": "This report could not be processed.",
}

CLOSURE_REASON_CODES: dict[str, str] = {
    "CONFIRMED_COMPLETE": "This report has been closed.",
    "ADMINISTRATIVE_CLOSE": "This report has been closed.",
    "NO_FURTHER_ACTION": "No further municipal action is planned.",
}

WORK_ORDER_CANCEL_REASON_CODES: dict[str, str] = {
    "CREATED_IN_ERROR": "Work order was created in error.",
    "NO_LONGER_NEEDED": "Work is no longer needed.",
    "UNABLE_TO_PERFORM": "The assigned crew could not perform the work.",
    "DUPLICATE_WORK": "Work duplicated an existing work order.",
}

STAFF_REASON_LABELS: dict[str, str] = {
    "WORK_COMPLETED": "Work completed as requested",
    "TEMPORARY_FIX": "Temporary repair applied",
    "NO_WORK_REQUIRED": "No municipal work required",
    "REFERRED_EXTERNAL": "Referred to another authority",
    "DUPLICATE_RESOLVED": "Resolved as a duplicate",
    "OUT_OF_SCOPE": "Outside municipal responsibility",
    "INSUFFICIENT_INFORMATION": "Insufficient information",
    "DUPLICATE": "Duplicate of an existing report",
    "INVALID_REPORT": "Not a valid municipal issue",
    "CITIZEN_WITHDRAWN": "Citizen withdrew the report",
    "SPAM": "Spam or abusive report",
    "CONFIRMED_COMPLETE": "Resolution confirmed, case closed",
    "ADMINISTRATIVE_CLOSE": "Closed after resolution for records",
    "NO_FURTHER_ACTION": "No further municipal action",
    "CREATED_IN_ERROR": "Created in error",
    "NO_LONGER_NEEDED": "No longer needed",
    "UNABLE_TO_PERFORM": "Unable to perform the work",
    "DUPLICATE_WORK": "Duplicate work order",
}


class OutcomeReasonError(ValueError):
    def __init__(self, message: str, *, code: str = "INVALID_OUTCOME_REASON") -> None:
        super().__init__(message)
        self.code = code


def required_outcome_kind(
    current_status: TicketStatus | str, requested_status: TicketStatus | str
) -> OutcomeKind | None:
    if requested_status == "RESOLVED":
        return "resolution"
    if requested_status != "CLOSED":
        return None
    if current_status == "RESOLVED":
        return "closure"
    if current_status in {"SUBMITTED", "UNDER_REVIEW"}:
        return "rejection"
    return None


def codes_for_kind(kind: OutcomeKind) -> dict[str, str]:
    if kind == "resolution":
        return RESOLUTION_REASON_CODES
    if kind == "rejection":
        return REJECTION_REASON_CODES
    return CLOSURE_REASON_CODES


def citizen_safe_message(code: str | None) -> str | None:
    if not code:
        return None
    return (
        RESOLUTION_REASON_CODES.get(code)
        or REJECTION_REASON_CODES.get(code)
        or CLOSURE_REASON_CODES.get(code)
    )


def normalize_private_note(note: str | None) -> str | None:
    if note is None:
        return None
    trimmed = note.strip()
    if not trimmed:
        return None
    if len(trimmed) > PRIVATE_NOTE_MAX_LENGTH:
        raise OutcomeReasonError(
            f"Private note must be at most {PRIVATE_NOTE_MAX_LENGTH} characters.",
            code="VALIDATION_ERROR",
        )
    return trimmed


def validate_outcome_reason(
    current_status: TicketStatus | str,
    requested_status: TicketStatus | str,
    reason_code: str | None,
) -> str | None:
    kind = required_outcome_kind(current_status, requested_status)
    if kind is None:
        return None
    cleaned = (reason_code or "").strip()
    if not cleaned:
        raise OutcomeReasonError(
            f"A structured {kind} reason is required to move this ticket to {requested_status}.",
            code="OUTCOME_REASON_REQUIRED",
        )
    allowed = codes_for_kind(kind)
    if cleaned not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise OutcomeReasonError(
            f"Invalid {kind} reason. Allowed codes: {allowed_list}.",
            code="INVALID_OUTCOME_REASON",
        )
    return cleaned


def validate_work_order_cancel_reason(reason_code: str | None) -> str:
    cleaned = (reason_code or "").strip()
    if not cleaned:
        raise OutcomeReasonError(
            "A structured cancel reason is required.",
            code="OUTCOME_REASON_REQUIRED",
        )
    if cleaned not in WORK_ORDER_CANCEL_REASON_CODES:
        allowed_list = ", ".join(sorted(WORK_ORDER_CANCEL_REASON_CODES))
        raise OutcomeReasonError(
            f"Invalid work-order cancel reason. Allowed codes: {allowed_list}.",
            code="INVALID_OUTCOME_REASON",
        )
    return cleaned
