from __future__ import annotations

from threading import Lock
from typing import Any, Literal

from app.database.serialization import (
    build_public_sort_key,
    build_staff_sort_key,
    is_public_ticket_publishable,
)
from app.database.ticket_patch import resolve_ticket_attr_name
from app.database.ticket_store import StaffTicketPage, TicketHistoryPage
from app.schemas.stored_ticket import StoredTicket
from app.schemas.ticket_response import TicketStatus
from app.services.complaints.ticket_list_filters import TicketListFilters, filter_stored_tickets
from app.utils.ticket_ids import normalize_tracking_code


class InMemoryTicketStore:
    def __init__(self) -> None:
        self._tickets: dict[str, StoredTicket] = {}
        self._tickets_by_number: dict[str, str] = {}
        self._ticket_numbers: set[str] = set()
        self._tracking_codes: set[str] = set()
        self._sequence = 0
        self._lock = Lock()

    def next_sequence(self) -> int:
        with self._lock:
            self._sequence += 1
            return self._sequence

    def save(self, ticket: StoredTicket) -> None:
        with self._lock:
            existing = self._tickets.get(ticket.ticket_id)
            if existing is not None:
                self._tickets_by_number.pop(existing.ticket_number.upper(), None)
            self._tickets[ticket.ticket_id] = ticket
            self._tickets_by_number[ticket.ticket_number.upper()] = ticket.ticket_id
            self._ticket_numbers.add(ticket.ticket_number)
            self._tracking_codes.add(ticket.tracking_code)

    def get(self, ticket_id: str) -> StoredTicket | None:
        with self._lock:
            return self._tickets.get(ticket_id)

    def get_by_tracking_code(self, tracking_code: str) -> StoredTicket | None:
        normalized = normalize_tracking_code(tracking_code)
        with self._lock:
            return next(
                (
                    ticket
                    for ticket in self._tickets.values()
                    if ticket.tracking_code.upper() == normalized
                ),
                None,
            )

    def get_by_ticket_number(self, ticket_number: str) -> StoredTicket | None:
        normalized = ticket_number.strip().upper()
        with self._lock:
            ticket_id = self._tickets_by_number.get(normalized)
            if ticket_id is None:
                return None
            return self._tickets.get(ticket_id)

    def list(self) -> list[StoredTicket]:
        with self._lock:
            return list(self._tickets.values())

    def list_staff_page(
        self,
        *,
        browse_mode: Literal["admin", "municipality"],
        municipality_id: str | None,
        department_ids: list[str] | None,
        limit: int,
        cursor: str | None,
        status: str | None = None,
        category: str | None = None,
        urgency: str | None = None,
        department_id: str | None = None,
        assignment_state: Literal["assigned", "unassigned"] | None = None,
        q: str | None = None,
        open_only: bool = False,
    ) -> StaffTicketPage:
        cursor_key = _decode_staff_cursor(cursor)
        with self._lock:
            candidates = list(self._tickets.values())

        if browse_mode == "admin":
            scoped = candidates
        else:
            scoped = [
                ticket
                for ticket in candidates
                if _municipal_staff_can_access(ticket, municipality_id, department_ids)
            ]

        filters = TicketListFilters(
            status=status,  # type: ignore[arg-type]
            category=category,
            urgency=urgency,  # type: ignore[arg-type]
            department_id=department_id,
            assignment_state=assignment_state,
            q=q,
            open_only=open_only,
        )
        filtered = filter_stored_tickets(scoped, filters)
        filtered.sort(key=_staff_sort_tuple, reverse=True)
        scanned_count = len(filtered)

        if cursor_key is not None:
            filtered = [ticket for ticket in filtered if _staff_sort_tuple(ticket) < cursor_key]

        page = filtered[:limit]
        next_cursor = (
            _encode_staff_cursor(build_staff_sort_key(page[-1]))
            if len(filtered) > limit and page
            else None
        )
        return StaffTicketPage(page, next_cursor, scanned_count)

    def staff_continuation_cursor(
        self,
        ticket: StoredTicket,
        *,
        browse_mode: Literal["admin", "municipality"],
        municipality_id: str | None,
        department_id: str | None = None,
    ) -> str:
        del browse_mode, municipality_id, department_id
        return _encode_staff_cursor(build_staff_sort_key(ticket))

    def list_by_owner(
        self,
        owner_user_id: str,
        *,
        limit: int,
        cursor: str | None = None,
    ) -> TicketHistoryPage:
        cursor_key = _decode_owner_history_cursor(cursor)
        with self._lock:
            owned = [
                ticket for ticket in self._tickets.values() if ticket.owner_user_id == owner_user_id
            ]
        owned.sort(key=_owner_history_sort_key, reverse=True)
        if cursor_key is not None:
            owned = [ticket for ticket in owned if _owner_history_sort_key(ticket) < cursor_key]

        page = owned[:limit]
        next_cursor = (
            _encode_owner_history_cursor(_owner_history_sort_key(page[-1]))
            if len(owned) > limit and page
            else None
        )
        return TicketHistoryPage(page, next_cursor)

    def list_public(
        self,
        *,
        limit: int,
        cursor: str | None = None,
    ) -> TicketHistoryPage:
        cursor_key = _decode_public_cursor(cursor)
        with self._lock:
            publishable = [
                ticket for ticket in self._tickets.values() if is_public_ticket_publishable(ticket)
            ]
        publishable.sort(key=_public_sort_key, reverse=True)
        if cursor_key is not None:
            publishable = [
                ticket for ticket in publishable if _public_sort_key(ticket) < cursor_key
            ]

        page = publishable[:limit]
        next_cursor = (
            _encode_public_cursor(_public_sort_key(page[-1]))
            if len(publishable) > limit and page
            else None
        )
        return TicketHistoryPage(page, next_cursor)

    def public_continuation_cursor(self, ticket: StoredTicket) -> str:
        return _encode_public_cursor(_public_sort_key(ticket))

    def patch_fields(
        self,
        ticket_id: str,
        fields: dict[str, Any],
    ) -> StoredTicket | None:
        if not fields:
            raise ValueError("At least one field is required for a ticket patch.")
        # Validate field names early (mirrors DynamoDB path).
        for field_name in fields:
            resolve_ticket_attr_name(field_name)

        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                return None
            updated_ticket = ticket.model_copy(update=fields)
            self._tickets[ticket_id] = updated_ticket
            return updated_ticket

    def update_status(
        self,
        ticket_id: str,
        status: TicketStatus,
        updated_at: str,
    ) -> StoredTicket | None:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                return None

            updated_ticket = ticket.model_copy(
                update={
                    "status": status,
                    "updated_at": updated_at,
                },
            )
            self._tickets[ticket_id] = updated_ticket
            return updated_ticket

    def claim_ai_processing(
        self,
        ticket_id: str,
        updated_at: str,
        claim_token: str | None = None,
    ) -> StoredTicket | None:
        """Atomically claim a pending ticket for AI work (pending → processing)."""
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None or ticket.ai_processing_status != "pending":
                return None
            updated_ticket = ticket.model_copy(
                update={
                    "ai_processing_status": "processing",
                    "ai_processing_claim_token": claim_token,
                    "updated_at": updated_at,
                },
            )
            self._tickets[ticket_id] = updated_ticket
            return updated_ticket

    def release_ai_processing_claim(
        self,
        ticket_id: str,
        updated_at: str,
    ) -> StoredTicket | None:
        """Return a stuck processing claim to pending so recovery can reclaim it."""
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None or ticket.ai_processing_status != "processing":
                return None
            updated_ticket = ticket.model_copy(
                update={
                    "ai_processing_status": "pending",
                    "ai_processing_claim_token": None,
                    "updated_at": updated_at,
                },
            )
            self._tickets[ticket_id] = updated_ticket
            return updated_ticket

    def requeue_ai_processing(self, ticket_id: str, updated_at: str) -> StoredTicket | None:
        """Reset a non-completed AI attempt so the durable job can retry it."""
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None or ticket.ai_processing_status == "completed":
                return None
            updated_ticket = ticket.model_copy(
                update={
                    "ai_processing_status": "pending",
                    "ai_processing_claim_token": None,
                    "updated_at": updated_at,
                }
            )
            self._tickets[ticket_id] = updated_ticket
            return updated_ticket

    def patch_ai_fields(
        self, ticket_id: str, claim_token: str, fields: dict[str, object]
    ) -> StoredTicket | None:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if (
                ticket is None
                or ticket.ai_processing_status != "processing"
                or ticket.ai_processing_claim_token != claim_token
            ):
                return None
            updated = ticket.model_copy(update={**fields, "ai_processing_claim_token": None})
            self._tickets[ticket_id] = updated
            return updated

    def claim_image_redaction(
        self, ticket_id: str, generation: int, claim_token: str, updated_at: str
    ) -> StoredTicket | None:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if (
                ticket is None
                or ticket.image_redaction_generation != generation
                or ticket.image_redaction_status != "pending"
            ):
                return None
            updated = ticket.model_copy(
                update={
                    "image_redaction_status": "processing",
                    "image_redaction_claim_token": claim_token,
                    "updated_at": updated_at,
                }
            )
            self._tickets[ticket_id] = updated
            return updated

    def finalize_image_redaction(
        self, ticket_id: str, generation: int, claim_token: str, fields: dict[str, Any]
    ) -> StoredTicket | None:
        for field_name in fields:
            resolve_ticket_attr_name(field_name)
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if (
                ticket is None
                or ticket.image_redaction_generation != generation
                or ticket.image_redaction_status != "processing"
                or ticket.image_redaction_claim_token != claim_token
            ):
                return None
            updated = ticket.model_copy(update={**fields, "image_redaction_claim_token": None})
            self._tickets[ticket_id] = updated
            return updated

    def requeue_image_redaction(
        self, ticket_id: str, generation: int, claim_token: str, updated_at: str
    ) -> StoredTicket | None:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if (
                ticket is None
                or ticket.image_redaction_generation != generation
                or ticket.image_redaction_status != "processing"
                or ticket.image_redaction_claim_token != claim_token
            ):
                return None
            updated = ticket.model_copy(
                update={
                    "image_redaction_status": "pending",
                    "image_redaction_claim_token": None,
                    "updated_at": updated_at,
                }
            )
            self._tickets[ticket_id] = updated
            return updated

    def start_image_reprocessing(self, ticket_id: str, updated_at: str) -> StoredTicket | None:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                return None
            updated = ticket.model_copy(
                update={
                    "image_redaction_generation": ticket.image_redaction_generation + 1,
                    "image_redaction_status": "pending",
                    "image_redaction_claim_token": None,
                    "image_redaction_completed_at": None,
                    "image_redaction_reason_code": None,
                    "updated_at": updated_at,
                }
            )
            self._tickets[ticket_id] = updated
            return updated

    def has_ticket_id(self, ticket_id: str) -> bool:
        with self._lock:
            return ticket_id in self._tickets

    def has_ticket_number(self, ticket_number: str) -> bool:
        with self._lock:
            return ticket_number in self._ticket_numbers

    def has_tracking_code(self, tracking_code: str) -> bool:
        normalized = normalize_tracking_code(tracking_code)
        with self._lock:
            return any(code.upper() == normalized for code in self._tracking_codes)

    def clear(self) -> None:
        with self._lock:
            self._tickets.clear()
            self._tickets_by_number.clear()
            self._ticket_numbers.clear()
            self._tracking_codes.clear()
            self._sequence = 0


ticket_store = InMemoryTicketStore()


def _owner_history_sort_key(ticket: StoredTicket) -> tuple[str, str]:
    return (ticket.created_at, ticket.ticket_id)


def _public_sort_key(ticket: StoredTicket) -> tuple[str, str]:
    return (build_public_sort_key(ticket), ticket.ticket_id)


def _encode_owner_history_cursor(sort_key: tuple[str, str]) -> str:
    import base64
    import json

    payload = {"createdAt": sort_key[0], "ticketId": sort_key[1]}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_owner_history_cursor(cursor: str | None) -> tuple[str, str] | None:
    if cursor is None or cursor == "":
        return None
    import base64
    import binascii
    import json

    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
        created_at = payload["createdAt"]
        ticket_id = payload["ticketId"]
    except (binascii.Error, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid owner history cursor.") from exc
    if not isinstance(created_at, str) or not isinstance(ticket_id, str):
        raise ValueError("Invalid owner history cursor.")
    return (created_at, ticket_id)


def _encode_public_cursor(sort_key: tuple[str, str]) -> str:
    import base64
    import json

    payload = {"publicSortKey": sort_key[0], "ticketId": sort_key[1]}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_public_cursor(cursor: str | None) -> tuple[str, str] | None:
    if cursor is None or cursor == "":
        return None
    import base64
    import binascii
    import json

    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
        public_sort_key = payload["publicSortKey"]
        ticket_id = payload["ticketId"]
    except (binascii.Error, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid public ticket cursor.") from exc
    if not isinstance(public_sort_key, str) or not isinstance(ticket_id, str):
        raise ValueError("Invalid public ticket cursor.")
    return (public_sort_key, ticket_id)


def _staff_sort_tuple(ticket: StoredTicket) -> tuple[str, str]:
    return (ticket.created_at, ticket.ticket_id)


def _municipal_staff_can_access(
    ticket: StoredTicket,
    municipality_id: str | None,
    department_ids: list[str] | None,
) -> bool:
    """Mirror ``staff_can_access_ticket`` for municipal browse without a principal."""
    if ticket.municipality_id is not None and ticket.municipality_id != municipality_id:
        return False
    if ticket.department_id is None:
        return True
    return ticket.department_id in set(department_ids or [])


def _encode_staff_cursor(staff_sort_key: str) -> str:
    import base64
    import json

    payload = {"staffSortKey": staff_sort_key}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_staff_cursor(cursor: str | None) -> tuple[str, str] | None:
    if cursor is None or cursor == "":
        return None
    import base64
    import binascii
    import json

    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
        staff_sort_key = payload["staffSortKey"]
    except (binascii.Error, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid staff ticket cursor.") from exc
    if not isinstance(staff_sort_key, str) or "#" not in staff_sort_key:
        raise ValueError("Invalid staff ticket cursor.")
    created_at, ticket_id = staff_sort_key.split("#", 1)
    if not created_at or not ticket_id:
        raise ValueError("Invalid staff ticket cursor.")
    return (created_at, ticket_id)
