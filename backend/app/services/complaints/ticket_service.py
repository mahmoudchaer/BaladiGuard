import logging
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock

from app.config import get_settings
from app.database.duplicate_group_store import DuplicateGroupStore
from app.database.status_history_store import StatusHistoryStore
from app.database.store_factory import (
    get_duplicate_group_store,
    get_status_history_store,
    get_ticket_store,
)
from app.database.ticket_store import TicketStore
from app.schemas.classification import ClassificationResult
from app.schemas.cleaning import CleaningResult
from app.schemas.stored_duplicate_group import StoredDuplicateGroup
from app.schemas.stored_status_history import StoredStatusHistory
from app.schemas.stored_ticket import PENDING_CLASSIFICATION, StoredTicket
from app.schemas.ticket import SubmitTicketRequest, SubmitTicketResponse
from app.schemas.ticket_ai_update import ReviewTicketCategoryRequest, SaveTicketAiOutputRequest
from app.schemas.ticket_merge import MergeDuplicateTicketsRequest
from app.schemas.ticket_response import (
    TicketDuplicateReference,
    TicketDuplicateSuggestion,
    TicketResponse,
    UpdateTicketStatusRequest,
)
from app.schemas.ticket_status import TicketStatus
from app.services.ai.classify import classify_complaint
from app.services.ai.clean import clean_report_description
from app.services.complaints.status_workflow import validate_status_transition
from app.services.complaints.ticket_read_mapper import map_ticket_to_response
from app.services.duplicates import find_nearby_duplicates
from app.services.urgency import score_urgency
from app.utils.ticket_ids import (
    generate_duplicate_group_id,
    generate_status_history_id,
    generate_ticket_id,
    generate_ticket_number,
    generate_tracking_code,
)

logger = logging.getLogger(__name__)

Classifier = Callable[..., ClassificationResult]
DescriptionCleaner = Callable[..., CleaningResult]


def _parse_iso_utc(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class TicketNotFoundError(LookupError):
    pass


class DuplicateMergeError(ValueError):
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


class TicketService:
    def __init__(
        self,
        store: TicketStore,
        history_store: StatusHistoryStore,
        duplicate_group_store: DuplicateGroupStore | None = None,
        *,
        classifier: Classifier = classify_complaint,
        description_cleaner: DescriptionCleaner = clean_report_description,
    ) -> None:
        self._store = store
        self._history_store = history_store
        self._duplicate_group_store = duplicate_group_store or get_duplicate_group_store()
        self._classifier = classifier
        self._description_cleaner = description_cleaner
        self._processing_ticket_ids: set[str] = set()
        self._processing_lock = Lock()

    def submit_ticket(self, payload: SubmitTicketRequest) -> SubmitTicketResponse:
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
            contact=payload.contact,
            location=payload.location,
            imageObjectKey=payload.image_object_key,
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

    def list_tickets(self) -> list[TicketResponse]:
        tickets = sorted(
            self._store.list(),
            key=lambda ticket: (ticket.created_at, ticket.ticket_number),
            reverse=True,
        )
        return [self._map_ticket(ticket) for ticket in tickets]

    def get_ticket(self, ticket_id: str) -> TicketResponse | None:
        ticket = self._store.get(ticket_id)
        if ticket is None:
            return None
        return self._map_ticket(ticket)

    def update_ticket_status(
        self,
        ticket_id: str,
        payload: UpdateTicketStatusRequest,
    ) -> TicketResponse:
        ticket = self._store.get(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(ticket_id)

        validate_status_transition(ticket.status, payload.status)

        updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        # Partial update so concurrent merges/AI writes are not overwritten.
        updated_ticket = self._store.patch_fields(
            ticket_id,
            {
                "status": payload.status,
                "updated_at": updated_at,
                "updated_by": payload.updated_by,
            },
        )
        if updated_ticket is None:
            raise TicketNotFoundError(ticket_id)
        self._record_status_history(
            ticket_id=ticket_id,
            previous_status=ticket.status,
            new_status=payload.status,
            updated_by=payload.updated_by,
            note=payload.note,
            created_at=updated_at,
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

        # Partial update so concurrent staff merges keep duplicateGroupId.
        updated_ticket = self._store.patch_fields(ticket_id, update_fields)
        if updated_ticket is None:
            raise TicketNotFoundError(ticket_id)
        return self._map_ticket(updated_ticket)

    def review_ticket_category(
        self,
        ticket_id: str,
        payload: ReviewTicketCategoryRequest,
    ) -> TicketResponse:
        ticket = self._store.get(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(ticket_id)

        reviewed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        # Partial update so concurrent merges/AI writes are not overwritten.
        updated_ticket = self._store.patch_fields(
            ticket_id,
            {
                "final_category": payload.final_category,
                "category": payload.final_category,
                "category_reviewed_by": payload.category_reviewed_by,
                "category_reviewed_at": reviewed_at,
                "updated_at": reviewed_at,
                "updated_by": payload.category_reviewed_by,
            },
        )
        if updated_ticket is None:
            raise TicketNotFoundError(ticket_id)
        return self._map_ticket(updated_ticket)

    def merge_duplicate_tickets(
        self,
        payload: MergeDuplicateTicketsRequest,
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

        duplicates: list[StoredTicket] = []
        for ticket_id in duplicate_ids:
            ticket = self._store.get(ticket_id)
            if ticket is None:
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
                createdBy=payload.merged_by,
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
                        "updated_by": payload.merged_by,
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

        updated_canonical = self._store.get(canonical_id)
        if updated_canonical is None:
            raise TicketNotFoundError(canonical_id)
        return self._map_ticket(updated_canonical)

    def _map_ticket(self, ticket: StoredTicket) -> TicketResponse:
        history = self._history_store.list_by_ticket_id(ticket.ticket_id)
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
            duplicate_group=duplicate_group,
            duplicate_suggestions=self._duplicate_suggestions_for_ticket(ticket),
        )

    def _duplicate_suggestions_for_ticket(
        self,
        ticket: StoredTicket,
    ) -> list[TicketDuplicateSuggestion]:
        category = effective_ticket_category(ticket)
        if not category:
            return []

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
                "Duplicate suggestion lookup unavailable for ticket %s (%s).",
                ticket.ticket_id,
                type(exc).__name__,
            )
            return []

        suggestions: list[TicketDuplicateSuggestion] = []
        for match in result.matches:
            candidate = self._store.get(match.ticket_id)
            if (
                ticket.duplicate_group_id
                and candidate is not None
                and candidate.duplicate_group_id == ticket.duplicate_group_id
            ):
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


ticket_service = TicketService(get_ticket_store(), get_status_history_store())
