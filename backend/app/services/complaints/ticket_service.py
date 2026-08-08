import logging
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock

from app.config import get_settings
from app.core.staff_auth import StaffPrincipal, staff_can_access_ticket, staff_can_assign_department
from app.database.audit_history_store import AuditHistoryStore
from app.database.duplicate_group_store import DuplicateGroupStore
from app.database.serialization import is_public_ticket_publishable
from app.database.status_history_store import StatusHistoryStore
from app.database.store_factory import (
    get_audit_history_store,
    get_citizen_store,
    get_duplicate_group_store,
    get_status_history_store,
    get_ticket_store,
)
from app.database.ticket_store import TicketStore
from app.schemas.classification import ClassificationResult
from app.schemas.cleaning import CleaningResult
from app.schemas.staff_user import StaffRole
from app.schemas.stored_audit_history import AuditActionType, StoredAuditHistory
from app.schemas.stored_duplicate_group import StoredDuplicateGroup
from app.schemas.stored_status_history import StoredStatusHistory
from app.schemas.stored_ticket import PENDING_CLASSIFICATION, StoredTicket
from app.schemas.ticket import ReportContact, SubmitTicketRequest, SubmitTicketResponse
from app.schemas.ticket_ai_update import (
    AssignTicketDepartmentRequest,
    ReviewTicketCategoryRequest,
    SaveTicketAiOutputRequest,
)
from app.schemas.ticket_merge import MergeDuplicateTicketsRequest
from app.schemas.ticket_response import (
    CitizenTicketResponse,
    PublicTicketListResponse,
    PublicTicketResponse,
    TicketDuplicateReference,
    TicketDuplicateSuggestion,
    TicketResponse,
    UpdateTicketPublicContentRequest,
    UpdateTicketStatusRequest,
)
from app.schemas.ticket_status import TicketStatus
from app.services.ai.classify import classify_complaint
from app.services.ai.clean import clean_report_description
from app.services.complaints.status_workflow import (
    MissingDepartmentAssignmentError,
    validate_status_transition,
)
from app.services.complaints.ticket_list_filters import TicketListFilters, filter_stored_tickets
from app.services.complaints.ticket_read_mapper import (
    map_ticket_to_citizen_response,
    map_ticket_to_public_response,
    map_ticket_to_response,
)
from app.services.duplicates import find_nearby_duplicates
from app.services.notifications.adapters import NotificationRecipient
from app.services.notifications.recipients import ticket_notification_recipient
from app.services.routing import department_ids, suggest_department_id
from app.services.urgency import score_urgency
from app.utils.ticket_ids import (
    generate_audit_history_id,
    generate_duplicate_group_id,
    generate_status_history_id,
    generate_ticket_id,
    generate_ticket_number,
    generate_tracking_code,
)

logger = logging.getLogger(__name__)

Classifier = Callable[..., ClassificationResult]
DescriptionCleaner = Callable[..., CleaningResult]
PUBLIC_TICKET_DEFAULT_LIMIT = 20
PUBLIC_TICKET_MAX_LIMIT = 50


def _parse_iso_utc(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class TicketNotFoundError(LookupError):
    pass


class DuplicateMergeError(ValueError):
    pass


class StaffScopeForbiddenError(PermissionError):
    pass


class PublicContentUpdateError(ValueError):
    pass


def effective_ticket_category(ticket: StoredTicket) -> str | None:
    """Staff-reviewed category, else the AI suggestion, else the stored category if classified.

    Returns ``None`` while the ticket is still pending classification so callers
    can handle unclassified tickets explicitly instead of matching on the
    ``PENDING_CLASSIFICATION`` placeholder.
    """
    if ticket.final_category:
        return ticket.final_category
    if ticket.ai_suggested_category:
        return ticket.ai_suggested_category
    if ticket.category and ticket.category != PENDING_CLASSIFICATION:
        return ticket.category
    return None


def _should_apply_department_suggestion(
    ticket: StoredTicket,
    *,
    previous_category_id: str | None,
) -> bool:
    """Apply an automatic suggestion to ``department_id`` only when not staff-overridden.

    Prefer comparing against the preserved ``suggested_department_id``. Fall back to the
    legacy category-map heuristic for tickets created before that field existed.
    """
    if ticket.department_id is None:
        return True
    if ticket.suggested_department_id is not None:
        return ticket.department_id == ticket.suggested_department_id
    previous_department_id = suggest_department_id(category_id=previous_category_id)
    return previous_department_id is not None and ticket.department_id == previous_department_id


def _department_suggestion_fields(
    ticket: StoredTicket,
    *,
    suggested_department_id: str | None,
    previous_category_id: str | None,
) -> dict[str, object]:
    if suggested_department_id is None:
        return {}
    fields: dict[str, object] = {"suggested_department_id": suggested_department_id}
    if _should_apply_department_suggestion(
        ticket,
        previous_category_id=previous_category_id,
    ):
        fields["department_id"] = suggested_department_id
    return fields


class TicketService:
    def __init__(
        self,
        store: TicketStore,
        history_store: StatusHistoryStore,
        duplicate_group_store: DuplicateGroupStore | None = None,
        audit_store: AuditHistoryStore | None = None,
        *,
        classifier: Classifier = classify_complaint,
        description_cleaner: DescriptionCleaner = clean_report_description,
    ) -> None:
        self._store = store
        self._history_store = history_store
        self._duplicate_group_store = duplicate_group_store or get_duplicate_group_store()
        self._audit_store = audit_store or get_audit_history_store()
        self._classifier = classifier
        self._description_cleaner = description_cleaner
        self._processing_ticket_ids: set[str] = set()
        self._processing_lock = Lock()

    def submit_ticket(
        self,
        payload: SubmitTicketRequest,
        *,
        owner_user_id: str,
        contact: ReportContact,
    ) -> SubmitTicketResponse:
        ticket_id = generate_ticket_id()
        ticket_number = generate_ticket_number(self._store.next_sequence())
        tracking_code = generate_tracking_code()
        created_at = datetime.now(UTC)
        created_at_iso = created_at.isoformat().replace("+00:00", "Z")

        stored_ticket = StoredTicket(
            ticketId=ticket_id,
            ticketNumber=ticket_number,
            trackingCode=tracking_code,
            description=payload.description,
            originalDescription=payload.description,
            contact=contact,
            location=payload.location,
            imageObjectKey=payload.image_object_key,
            ownerUserId=owner_user_id,
            status="SUBMITTED",
            category=PENDING_CLASSIFICATION,
            aiProcessingStatus="pending",
            createdAt=created_at_iso,
            updatedAt=created_at_iso,
        )
        self._store.save(stored_ticket)
        self._record_status_history(
            ticket_id=ticket_id,
            previous_status=None,
            new_status="SUBMITTED",
            updated_by=None,
            note="Ticket submitted.",
            created_at=created_at_iso,
        )

        self._emit_notification_safe(
            event="ticket_created",
            ticket_id=ticket_id,
            status="SUBMITTED",
            tracking_code=tracking_code,
            ticket_number=ticket_number,
            recipient=ticket_notification_recipient(stored_ticket),
        )

        return SubmitTicketResponse(
            ticketId=ticket_id,
            ticketNumber=ticket_number,
            trackingCode=tracking_code,
            status="SUBMITTED",
            message="Your report was submitted successfully.",
            createdAt=created_at_iso,
        )

    def process_ticket_ai(self, ticket_id: str) -> bool:
        """Process one pending ticket without exposing failures to the submit request.

        Returns ``True`` when this call persisted a terminal AI status. Repeated or
        concurrent calls for the same ticket are no-ops once another worker has claimed
        the ticket (``pending`` → ``processing``) or the stored status is already
        terminal.

        Ownership of the AI job is decided by a store-level conditional claim so
        multi-worker / redeploy races cannot both invoke Bedrock for the same ticket.
        """
        with self._processing_lock:
            if ticket_id in self._processing_ticket_ids:
                return False
            claimed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            ticket = self._store.claim_ai_processing(ticket_id, claimed_at)
            if ticket is None:
                return False
            self._processing_ticket_ids.add(ticket_id)

        try:
            classification = self._classifier(
                ticket.original_description or ticket.description,
                image_object_key=ticket.image_object_key,
            )
            cleaning = self._description_cleaner(
                ticket.original_description or ticket.description,
            )

            classification_ok = not classification.used_fallback
            cleaning_ok = not cleaning.used_fallback
            # Keep every successful partial result; "failed" only means no AI output
            # was produced at all. A valid category must never be discarded because
            # cleaning fell back (or vice versa).
            processing_failed = not classification_ok and not cleaning_ok
            urgency = self._score_ticket_urgency(
                ticket=ticket,
                category=classification.category if classification_ok else None,
                description=cleaning.cleaned_description if cleaning_ok else None,
            )
            self.save_ticket_ai_output(
                ticket_id,
                SaveTicketAiOutputRequest(
                    cleanedDescription=cleaning.cleaned_description if cleaning_ok else None,
                    aiSuggestedCategory=(classification.category if classification_ok else None),
                    aiCategoryExplanation=(
                        classification.explanation if classification_ok else None
                    ),
                    aiModelVersion=get_settings().bedrock_model_id,
                    urgencyScore=urgency.urgency_score,
                    urgencyReason=urgency.urgency_reason,
                    priority=urgency.urgency_level,
                    aiProcessingStatus="failed" if processing_failed else "completed",
                ),
            )
            if processing_failed:
                logger.warning(
                    "AI processing produced no output for ticket %s.",
                    ticket_id,
                )
            elif not (classification_ok and cleaning_ok):
                logger.warning(
                    "AI processing partially succeeded for ticket %s "
                    "(classification_ok=%s, cleaning_ok=%s).",
                    ticket_id,
                    classification_ok,
                    cleaning_ok,
                )
            return True
        except Exception as exc:
            logger.error(
                "AI processing failed for ticket %s (%s).",
                ticket_id,
                type(exc).__name__,
            )
            try:
                urgency = self._score_ticket_urgency(ticket=ticket)
                self.save_ticket_ai_output(
                    ticket_id,
                    SaveTicketAiOutputRequest(
                        urgencyScore=urgency.urgency_score,
                        urgencyReason=urgency.urgency_reason,
                        priority=urgency.urgency_level,
                        aiProcessingStatus="failed",
                    ),
                )
            except Exception as persistence_exc:
                logger.error(
                    "Could not persist failed AI status for ticket %s (%s).",
                    ticket_id,
                    type(persistence_exc).__name__,
                )
            return True
        finally:
            with self._processing_lock:
                self._processing_ticket_ids.discard(ticket_id)

    def recover_pending_ai_tickets(self) -> int:
        """Reprocess tickets stuck in ``pending`` or stale ``processing`` after a crash.

        Called on application startup so a fire-and-forget background task that died
        between the 201 response and the terminal AI status does not leave tickets
        unmanageable.

        Fresh ``processing`` claims are left alone so a rolling deploy / multi-worker
        startup cannot steal a ticket another worker is still handling. Only claims
        whose ``updatedAt`` is older than ``AI_PROCESSING_CLAIM_TIMEOUT_SECONDS`` are
        released back to ``pending`` and reclaimed. Returns the number of tickets that
        reached a terminal status.
        """
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat().replace("+00:00", "Z")
        recoverable_ids: list[str] = []
        skipped_active_claims = 0

        for ticket in self._store.list():
            status = ticket.ai_processing_status
            if status == "pending":
                recoverable_ids.append(ticket.ticket_id)
                continue
            if status != "processing":
                continue
            if not self._is_stale_ai_processing_claim(ticket, now=now_dt):
                skipped_active_claims += 1
                continue
            released = self._store.release_ai_processing_claim(ticket.ticket_id, now)
            if released is not None:
                recoverable_ids.append(ticket.ticket_id)

        recovered = 0
        for ticket_id in recoverable_ids:
            if self.process_ticket_ai(ticket_id):
                recovered += 1
        if recoverable_ids or skipped_active_claims:
            logger.info(
                "AI pending recovery processed %d of %d recoverable ticket(s) "
                "(skipped %d active processing claim(s)).",
                recovered,
                len(recoverable_ids),
                skipped_active_claims,
            )
        return recovered

    def _is_stale_ai_processing_claim(
        self,
        ticket: StoredTicket,
        *,
        now: datetime,
    ) -> bool:
        """Return True when a processing claim is old enough to safely reclaim."""
        claimed_at = _parse_iso_utc(ticket.updated_at)
        if claimed_at is None:
            # Unparseable timestamps should not leave tickets permanently stuck.
            return True
        age_seconds = (now - claimed_at.astimezone(UTC)).total_seconds()
        return age_seconds >= get_settings().ai_processing_claim_timeout_seconds

    def list_tickets(
        self,
        filters: TicketListFilters | None = None,
        *,
        staff_principal: StaffPrincipal | None = None,
    ) -> list[TicketResponse]:
        stored_tickets = filter_stored_tickets(self._store.list(), filters)
        if staff_principal is not None:
            stored_tickets = [
                ticket
                for ticket in stored_tickets
                if staff_can_access_ticket(staff_principal, ticket)
            ]
        tickets = sorted(
            stored_tickets,
            key=lambda ticket: (ticket.created_at, ticket.ticket_number),
            reverse=True,
        )
        return [self._map_ticket(ticket) for ticket in tickets]

    def list_public_tickets(
        self,
        *,
        limit: int = PUBLIC_TICKET_DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> PublicTicketListResponse:
        page_size = min(max(limit, 1), PUBLIC_TICKET_MAX_LIMIT)
        page = self._store.list_public(limit=page_size, cursor=cursor)
        owners = self._public_owner_cache(page.items)
        return PublicTicketListResponse(
            items=[
                map_ticket_to_public_response(ticket, owner=owners.get(ticket.owner_user_id))
                for ticket in page.items
            ],
            nextCursor=page.next_cursor,
            limit=page_size,
        )

    def get_public_ticket(self, ticket_number: str) -> PublicTicketResponse | None:
        ticket = self._store.get_by_ticket_number(ticket_number)
        if ticket is None or not self._is_public_ticket_publishable(ticket):
            return None
        owner = get_citizen_store().get(ticket.owner_user_id) if ticket.owner_user_id else None
        return map_ticket_to_public_response(ticket, owner=owner)

    def get_ticket(
        self,
        ticket_id: str,
        *,
        staff_principal: StaffPrincipal | None = None,
    ) -> TicketResponse | None:
        ticket = self._store.get(ticket_id)
        if ticket is None:
            return None
        if staff_principal is not None and not staff_can_access_ticket(staff_principal, ticket):
            return None
        return self._map_ticket(ticket, include_duplicate_suggestions=True)

    def get_ticket_by_tracking_code(self, tracking_code: str) -> CitizenTicketResponse | None:
        ticket = self._store.get_by_tracking_code(tracking_code)
        if ticket is None:
            return None
        history = self._history_store.list_by_ticket_id(ticket.ticket_id)
        return map_ticket_to_citizen_response(ticket, history)

    def _public_owner_cache(self, tickets: list[StoredTicket]):
        owner_ids = {ticket.owner_user_id for ticket in tickets if ticket.owner_user_id}
        if not owner_ids:
            return {}
        citizen_store = get_citizen_store()
        return {owner_id: citizen_store.get(owner_id) for owner_id in owner_ids}

    @staticmethod
    def _is_public_ticket_publishable(ticket: StoredTicket) -> bool:
        return is_public_ticket_publishable(ticket)

    def update_ticket_status(
        self,
        ticket_id: str,
        payload: UpdateTicketStatusRequest,
        *,
        staff_principal: StaffPrincipal | None = None,
    ) -> TicketResponse:
        ticket = self._store.get(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(ticket_id)
        if staff_principal is not None and not staff_can_access_ticket(staff_principal, ticket):
            raise TicketNotFoundError(ticket_id)

        validate_status_transition(ticket.status, payload.status)
        if payload.status == "ASSIGNED" and ticket.department_id not in department_ids():
            raise MissingDepartmentAssignmentError()

        actor_id, actor_role = self._verified_actor(staff_principal, payload.updated_by)
        updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        # Partial update so concurrent merges/AI writes are not overwritten.
        updated_ticket = self._store.patch_fields(
            ticket_id,
            {
                "status": payload.status,
                "updated_at": updated_at,
                "updated_by": actor_id,
            },
        )
        if updated_ticket is None:
            raise TicketNotFoundError(ticket_id)
        self._record_status_history(
            ticket_id=ticket_id,
            previous_status=ticket.status,
            new_status=payload.status,
            updated_by=actor_id,
            note=payload.note,
            created_at=updated_at,
        )
        self._record_audit_history(
            ticket_id=ticket_id,
            action_type="STATUS_CHANGE",
            actor_id=actor_id,
            actor_role=actor_role,
            summary=f"Status changed from {ticket.status} to {payload.status}.",
            previous_value=ticket.status,
            new_value=payload.status,
            created_at=updated_at,
        )
        event = "ticket_resolved" if payload.status in {"RESOLVED", "CLOSED"} else "ticket_updated"
        self._emit_notification_safe(
            event=event,
            ticket_id=updated_ticket.ticket_id,
            status=payload.status,
            tracking_code=updated_ticket.tracking_code,
            ticket_number=updated_ticket.ticket_number,
            recipient=ticket_notification_recipient(updated_ticket),
        )
        return self._map_ticket(updated_ticket)

    def save_ticket_ai_output(
        self,
        ticket_id: str,
        payload: SaveTicketAiOutputRequest,
    ) -> TicketResponse:
        ticket = self._store.get(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(ticket_id)

        updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        update_fields: dict[str, object] = {
            "cleaned_description": payload.cleaned_description,
            "ai_suggested_category": payload.ai_suggested_category,
            "ai_category_explanation": payload.ai_category_explanation,
            "ai_model_version": payload.ai_model_version,
            "urgency_score": payload.urgency_score,
            "urgency_reason": payload.urgency_reason,
            "priority": payload.priority,
            "ai_processing_status": payload.ai_processing_status,
            "updated_at": updated_at,
        }
        if payload.ai_confidence is not None:
            update_fields["ai_confidence"] = payload.ai_confidence
        suggested_department_id = suggest_department_id(
            category_id=payload.ai_suggested_category,
            urgency_level=payload.priority,
            urgency_score=payload.urgency_score,
        )
        update_fields.update(
            _department_suggestion_fields(
                ticket,
                suggested_department_id=suggested_department_id,
                previous_category_id=ticket.ai_suggested_category,
            )
        )

        # Partial update so concurrent staff merges keep duplicateGroupId.
        updated_ticket = self._store.patch_fields(ticket_id, update_fields)
        if updated_ticket is None:
            raise TicketNotFoundError(ticket_id)
        return self._map_ticket(updated_ticket)

    def review_ticket_category(
        self,
        ticket_id: str,
        payload: ReviewTicketCategoryRequest,
        *,
        staff_principal: StaffPrincipal | None = None,
    ) -> TicketResponse:
        ticket = self._store.get(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(ticket_id)
        if staff_principal is not None and not staff_can_access_ticket(staff_principal, ticket):
            raise TicketNotFoundError(ticket_id)

        actor_id, actor_role = self._verified_actor(staff_principal, payload.category_reviewed_by)
        reviewed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        update_fields: dict[str, object] = {
            "final_category": payload.final_category,
            "category": payload.final_category,
            "category_reviewed_by": actor_id,
            "category_reviewed_at": reviewed_at,
            "updated_at": reviewed_at,
            "updated_by": actor_id,
        }
        suggested_department_id = suggest_department_id(category_id=payload.final_category)
        previous_category_id = effective_ticket_category(ticket)
        department_update_fields = _department_suggestion_fields(
            ticket,
            suggested_department_id=suggested_department_id,
            previous_category_id=previous_category_id,
        )
        department_id = department_update_fields.get("department_id")
        if (
            staff_principal is not None
            and isinstance(department_id, str)
            and not staff_can_assign_department(staff_principal, department_id)
        ):
            raise StaffScopeForbiddenError(department_id)
        update_fields.update(department_update_fields)

        # Partial update so concurrent merges/AI writes are not overwritten.
        updated_ticket = self._store.patch_fields(
            ticket_id,
            update_fields,
        )
        if updated_ticket is None:
            raise TicketNotFoundError(ticket_id)
        previous_category = ticket.final_category or ticket.category
        self._record_audit_history(
            ticket_id=ticket_id,
            action_type="CATEGORY_REVIEW",
            actor_id=actor_id,
            actor_role=actor_role,
            summary=f"Category reviewed as {payload.final_category}.",
            previous_value=previous_category,
            new_value=payload.final_category,
            created_at=reviewed_at,
        )
        return self._map_ticket(updated_ticket)

    def update_ticket_public_content(
        self,
        ticket_id: str,
        payload: UpdateTicketPublicContentRequest,
        *,
        staff_principal: StaffPrincipal | None = None,
    ) -> TicketResponse:
        """Persist staff-approved public projection fields, including public photo approval."""
        ticket = self._store.get(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(ticket_id)
        if staff_principal is not None and not staff_can_access_ticket(staff_principal, ticket):
            raise TicketNotFoundError(ticket_id)

        description = payload.public_description.strip()
        location_label = payload.public_location_label.strip()
        if payload.public_status == "PUBLISHED":
            if not ticket.final_category:
                raise PublicContentUpdateError(
                    "A staff-reviewed final category is required before publishing."
                )
            if not description or not location_label:
                raise PublicContentUpdateError(
                    "Published tickets require a public description and coarse location label."
                )

        actor_id, actor_role = self._verified_actor(staff_principal, payload.updated_by)
        updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        update_fields: dict[str, object] = {
            "public_status": payload.public_status,
            "public_description": description or None,
            "public_location_label": location_label or None,
            "updated_at": updated_at,
            "updated_by": actor_id,
        }

        # Only approve this ticket's bound upload, or clear. Never accept a caller-supplied key.
        if payload.clear_public_photo:
            update_fields["public_image_object_key"] = None
        elif payload.approve_original_photo:
            if not ticket.image_object_key:
                raise PublicContentUpdateError("This ticket has no original upload to approve.")
            update_fields["public_image_object_key"] = ticket.image_object_key

        if payload.public_status == "PUBLISHED":
            update_fields["public_published_at"] = ticket.public_published_at or updated_at
        elif payload.public_status in {"DRAFT", "UNPUBLISHED"} and ticket.public_published_at:
            # Keep historical publishedAt for audit; unpublish removes feed visibility via status.
            pass

        updated_ticket = self._store.patch_fields(ticket_id, update_fields)
        if updated_ticket is None:
            raise TicketNotFoundError(ticket_id)

        photo_note = "photo unchanged"
        if payload.clear_public_photo:
            photo_note = "public photo cleared"
        elif payload.approve_original_photo:
            photo_note = "original photo approved"

        self._record_audit_history(
            ticket_id=ticket_id,
            action_type="PUBLIC_CONTENT_UPDATE",
            actor_id=actor_id,
            actor_role=actor_role,
            summary=f"Public content set to {payload.public_status} ({photo_note}).",
            previous_value=ticket.public_status,
            new_value=payload.public_status,
            created_at=updated_at,
        )
        return self._map_ticket(updated_ticket)

    def assign_ticket_department(
        self,
        ticket_id: str,
        payload: AssignTicketDepartmentRequest,
        *,
        staff_principal: StaffPrincipal | None = None,
    ) -> TicketResponse:
        """Persist a staff department assignment without clearing the AI suggestion."""
        ticket = self._store.get(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(ticket_id)
        if staff_principal is not None:
            if not staff_can_access_ticket(staff_principal, ticket):
                raise TicketNotFoundError(ticket_id)
            if not staff_can_assign_department(staff_principal, payload.department_id):
                raise StaffScopeForbiddenError(payload.department_id)

        actor_id, actor_role = self._verified_actor(staff_principal, payload.updated_by)
        updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        updated_ticket = self._store.patch_fields(
            ticket_id,
            {
                "department_id": payload.department_id,
                "updated_at": updated_at,
                "updated_by": actor_id,
            },
        )
        if updated_ticket is None:
            raise TicketNotFoundError(ticket_id)
        self._record_audit_history(
            ticket_id=ticket_id,
            action_type="DEPARTMENT_ASSIGN",
            actor_id=actor_id,
            actor_role=actor_role,
            summary=(
                f"Department assignment changed from "
                f"{ticket.department_id or 'unassigned'} to {payload.department_id}."
            ),
            previous_value=ticket.department_id,
            new_value=payload.department_id,
            created_at=updated_at,
        )
        return self._map_ticket(updated_ticket)

    def merge_duplicate_tickets(
        self,
        payload: MergeDuplicateTicketsRequest,
        *,
        staff_principal: StaffPrincipal | None = None,
    ) -> TicketResponse:
        canonical_id = payload.canonical_ticket_id.strip()
        duplicate_ids = payload.duplicate_ticket_ids

        if canonical_id in duplicate_ids:
            raise DuplicateMergeError(
                "The main ticket cannot also appear in the duplicate ticket list."
            )

        canonical = self._store.get(canonical_id)
        if canonical is None:
            raise TicketNotFoundError(canonical_id)
        if staff_principal is not None and not staff_can_access_ticket(staff_principal, canonical):
            raise TicketNotFoundError(canonical_id)

        duplicates: list[StoredTicket] = []
        for ticket_id in duplicate_ids:
            ticket = self._store.get(ticket_id)
            if ticket is None:
                raise TicketNotFoundError(ticket_id)
            if staff_principal is not None and not staff_can_access_ticket(staff_principal, ticket):
                raise TicketNotFoundError(ticket_id)
            if ticket.duplicate_group_id:
                raise DuplicateMergeError(
                    f"Ticket {ticket_id} already belongs to a duplicate group. "
                    "Unlinking or regrouping existing members is not supported."
                )
            duplicates.append(ticket)

        canonical_category = effective_ticket_category(canonical)
        if canonical_category is None:
            raise DuplicateMergeError(
                "The main ticket has no reviewed or AI-suggested category yet. "
                "Merge is only allowed between classified tickets."
            )
        for ticket in duplicates:
            ticket_category = effective_ticket_category(ticket)
            if ticket_category is None:
                raise DuplicateMergeError(
                    f"Ticket {ticket.ticket_id} has no reviewed or AI-suggested category yet. "
                    "Merge is only allowed between classified tickets."
                )
            if ticket_category != canonical_category:
                raise DuplicateMergeError(
                    "All merged tickets must share the same category as the main ticket."
                )

        existing_group: StoredDuplicateGroup | None = None
        if canonical.duplicate_group_id:
            existing_group = self._duplicate_group_store.get(canonical.duplicate_group_id)
            if existing_group is not None and existing_group.canonical_ticket_id != canonical_id:
                raise DuplicateMergeError(
                    "This ticket is already grouped under main ticket "
                    f"{existing_group.canonical_ticket_id}. Merge additional duplicates "
                    "from the main ticket instead."
                )

        merged_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        actor_id, actor_role = self._verified_actor(staff_principal, payload.merged_by)
        if existing_group is not None:
            # Append to the staff-chosen main ticket's existing group.
            group_id = existing_group.duplicate_group_id
            member_ids = [*existing_group.ticket_ids]
            new_member_ids = [tid for tid in duplicate_ids if tid not in member_ids]
            group = existing_group.model_copy(update={"ticket_ids": member_ids + new_member_ids})
        else:
            group_id = canonical.duplicate_group_id or generate_duplicate_group_id()
            new_member_ids = duplicate_ids
            if not canonical.duplicate_group_id:
                new_member_ids = [canonical_id, *duplicate_ids]
            group = StoredDuplicateGroup(
                duplicateGroupId=group_id,
                canonicalTicketId=canonical_id,
                ticketIds=[canonical_id, *duplicate_ids],
                createdAt=merged_at,
                createdBy=actor_id,
            )

        # Stamp members first and persist the group row last so a failure never
        # leaves a saved group pointing at unstamped tickets. Partial attribute
        # patches also avoid races with background AI full-document writes.
        stamped: list[tuple[str, str | None]] = []
        try:
            for ticket_id in new_member_ids:
                previous = canonical.duplicate_group_id if ticket_id == canonical_id else None
                updated = self._store.patch_fields(
                    ticket_id,
                    {
                        "duplicate_group_id": group_id,
                        "updated_at": merged_at,
                        "updated_by": actor_id,
                    },
                )
                if updated is None:
                    raise TicketNotFoundError(ticket_id)
                stamped.append((ticket_id, previous))

            self._duplicate_group_store.save(group)
        except Exception:
            for ticket_id, previous_group_id in stamped:
                try:
                    self._store.patch_fields(
                        ticket_id,
                        {"duplicate_group_id": previous_group_id, "updated_at": merged_at},
                    )
                except Exception:  # pragma: no cover - best-effort rollback
                    logger.exception(
                        "Could not roll back duplicate group stamp for ticket %s.",
                        ticket_id,
                    )
            raise

        member_summary = ", ".join(group.ticket_ids)
        stamped_by_id = {ticket_id: previous for ticket_id, previous in stamped}
        audit_ticket_ids = [canonical_id, *[tid for tid, _ in stamped if tid != canonical_id]]
        for ticket_id in audit_ticket_ids:
            previous_group_id = stamped_by_id.get(ticket_id)
            if ticket_id == canonical_id and ticket_id not in stamped_by_id:
                previous_group_id = canonical.duplicate_group_id
            role = "canonical" if ticket_id == canonical_id else "duplicate"
            self._record_audit_history(
                ticket_id=ticket_id,
                action_type="DUPLICATE_MERGE",
                actor_id=actor_id,
                actor_role=actor_role,
                summary=(
                    f"Ticket marked as {role} in duplicate group {group_id} "
                    f"(members: {member_summary})."
                ),
                previous_value=previous_group_id,
                new_value=group_id,
                created_at=merged_at,
            )

        updated_canonical = self._store.get(canonical_id)
        if updated_canonical is None:
            raise TicketNotFoundError(canonical_id)
        return self._map_ticket(updated_canonical)

    def _map_ticket(
        self,
        ticket: StoredTicket,
        *,
        include_duplicate_suggestions: bool = False,
    ) -> TicketResponse:
        history = self._history_store.list_by_ticket_id(ticket.ticket_id)
        audit_history = self._list_audit_history_safe(ticket.ticket_id)
        duplicate_group = None
        if ticket.duplicate_group_id:
            stored_group = self._duplicate_group_store.get(ticket.duplicate_group_id)
            if stored_group is not None:
                duplicate_group = TicketDuplicateReference(
                    duplicateGroupId=stored_group.duplicate_group_id,
                    ticketIds=stored_group.ticket_ids,
                    canonicalTicketId=stored_group.canonical_ticket_id,
                )
            else:
                duplicate_group = TicketDuplicateReference(
                    duplicateGroupId=ticket.duplicate_group_id,
                )
        return map_ticket_to_response(
            ticket,
            history,
            audit_history=audit_history,
            duplicate_group=duplicate_group,
            duplicate_suggestions=(
                self._duplicate_suggestions_for_ticket(ticket)
                if include_duplicate_suggestions
                else []
            ),
        )

    def _duplicate_suggestions_for_ticket(
        self,
        ticket: StoredTicket,
    ) -> list[TicketDuplicateSuggestion]:
        category = effective_ticket_category(ticket)
        if not category:
            return []

        try:
            candidate_tickets = [
                candidate for candidate in self._store.list() if not candidate.duplicate_group_id
            ]
            result = find_nearby_duplicates(
                category=category,
                latitude=ticket.location.latitude,
                longitude=ticket.location.longitude,
                tickets=candidate_tickets,
                exclude_ticket_id=ticket.ticket_id,
            )
        except Exception as exc:
            logger.warning(
                "Duplicate suggestion lookup unavailable for ticket %s (%s).",
                ticket.ticket_id,
                type(exc).__name__,
            )
            return []

        suggestions: list[TicketDuplicateSuggestion] = []
        for match in result.matches:
            candidate = self._store.get(match.ticket_id)
            if candidate is not None and candidate.duplicate_group_id:
                continue

            suggestions.append(
                TicketDuplicateSuggestion(
                    ticketId=match.ticket_id,
                    ticketNumber=candidate.ticket_number if candidate is not None else None,
                    distanceMeters=match.distance_meters,
                    status=match.status,
                    category=match.category,
                    score=match.score,
                    categoryMatch=match.category_match,
                )
            )

        return suggestions

    def _score_ticket_urgency(
        self,
        *,
        ticket: StoredTicket,
        category: str | None = None,
        description: str | None = None,
    ):
        scoring_category = category or effective_ticket_category(ticket)
        scoring_description = description or ticket.original_description or ticket.description
        duplicate_count = self._nearby_duplicate_count(
            ticket=ticket,
            category=scoring_category,
        )
        return score_urgency(
            category=scoring_category,
            description=scoring_description,
            location=ticket.location,
            created_at=ticket.created_at,
            status=ticket.status,
            duplicate_count=duplicate_count,
            has_photo=bool(ticket.image_object_key),
        )

    def _nearby_duplicate_count(self, *, ticket: StoredTicket, category: str | None) -> int | None:
        if not category:
            return None

        try:
            result = find_nearby_duplicates(
                category=category,
                latitude=ticket.location.latitude,
                longitude=ticket.location.longitude,
                tickets=self._store.list(),
                exclude_ticket_id=ticket.ticket_id,
            )
        except Exception as exc:
            logger.warning(
                "Duplicate lookup unavailable while scoring urgency for ticket %s (%s).",
                ticket.ticket_id,
                type(exc).__name__,
            )
            return None
        return len(result.matches)

    def _emit_notification_safe(
        self,
        *,
        event: str,
        ticket_id: str,
        status: str,
        tracking_code: str | None = None,
        ticket_number: str | None = None,
        recipient: NotificationRecipient | None = None,
    ) -> None:
        """Best-effort notification emit; never breaks the ticket workflow."""
        if recipient is None:
            logger.info(
                "Notification skipped because no eligible recipient was resolved "
                "event=%s ticket_id=%s status=%s",
                event,
                ticket_id,
                status,
            )
            return
        try:
            from app.services.notifications import emit_ticket_notification

            emit_ticket_notification(
                event=event,
                ticket_id=ticket_id,
                status=status,
                tracking_code=tracking_code,
                ticket_number=ticket_number,
                recipient=recipient,
            )
        except Exception as exc:  # pragma: no cover - defensive outer guard
            logger.error(
                "Notification hook failed for ticket %s (%s).",
                ticket_id,
                type(exc).__name__,
            )

    def _verified_actor(
        self,
        staff_principal: StaffPrincipal | None,
        fallback_actor_id: str | None,
    ) -> tuple[str | None, StaffRole | None]:
        """Actor ID and role always prefer the authenticated principal over client fields."""
        if staff_principal is not None:
            return staff_principal.staff_id, staff_principal.role
        return fallback_actor_id, None

    def _record_status_history(
        self,
        *,
        ticket_id: str,
        previous_status: TicketStatus | None,
        new_status: TicketStatus,
        updated_by: str | None,
        note: str | None,
        created_at: str,
    ) -> None:
        entry = StoredStatusHistory(
            historyId=generate_status_history_id(),
            ticketId=ticket_id,
            previousStatus=previous_status,
            newStatus=new_status,
            updatedBy=updated_by,
            note=note,
            createdAt=created_at,
        )
        self._history_store.append(entry)

    def _record_audit_history(
        self,
        *,
        ticket_id: str,
        action_type: AuditActionType,
        actor_id: str | None,
        summary: str,
        previous_value: str | None,
        new_value: str | None,
        created_at: str,
        actor_role: StaffRole | None = None,
    ) -> None:
        """Persist a staff audit row without blocking the primary mutation on failure."""
        entry = StoredAuditHistory(
            auditId=generate_audit_history_id(),
            ticketId=ticket_id,
            actionType=action_type,
            actorId=actor_id,
            actorRole=actor_role,
            summary=summary,
            previousValue=previous_value,
            newValue=new_value,
            createdAt=created_at,
        )
        try:
            self._audit_store.append(entry)
        except Exception:
            logger.exception(
                "Audit history write failed for ticket %s action %s; primary mutation kept.",
                ticket_id,
                action_type,
            )

    def _list_audit_history_safe(self, ticket_id: str) -> list[StoredAuditHistory]:
        """Load audit rows for staff responses without failing the primary read/mutation."""
        try:
            return self._audit_store.list_by_ticket_id(ticket_id)
        except Exception:
            logger.exception(
                "Audit history read failed for ticket %s; returning empty auditHistory.",
                ticket_id,
            )
            return []


ticket_service = TicketService(get_ticket_store(), get_status_history_store())
