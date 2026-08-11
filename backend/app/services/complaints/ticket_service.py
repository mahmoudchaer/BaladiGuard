import logging
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock
from typing import Literal
from uuid import uuid4

from app.config import get_settings
from app.core.metrics import emit_metric
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
from app.schemas.staff_ticket_collection import (
    TicketAggregatesResponse,
    TicketListPageResponse,
    TicketMapClusterResponse,
    TicketMapMarkerResponse,
    TicketMapViewportResponse,
)
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
from app.services.complaints.sla import derive_ticket_sla
from app.services.complaints.status_workflow import (
    MissingDepartmentAssignmentError,
    validate_status_transition,
)
from app.services.complaints.ticket_list_filters import TicketListFilters, ticket_matches_filters
from app.services.complaints.ticket_read_mapper import (
    map_ticket_to_citizen_response,
    map_ticket_to_list_item,
    map_ticket_to_public_response,
    map_ticket_to_response,
)
from app.services.duplicates import OPEN_TICKET_STATUSES, find_nearby_duplicates
from app.services.notifications.adapters import NotificationRecipient
from app.services.notifications.recipients import ticket_notification_recipient
from app.services.routing import department_ids, suggest_department_id
from app.services.uploads.photo_upload_service import photo_upload_service
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
STAFF_TICKET_DEFAULT_LIMIT = 25
STAFF_TICKET_MAX_LIMIT = 100
STAFF_SLA_FILTER_MAX_ROUNDS = 20
STAFF_MAP_DEFAULT_LIMIT = 200
STAFF_MAP_MAX_LIMIT = 500
STAFF_MAP_MARKER_ZOOM = 14
STAFF_MAP_CANDIDATE_BUDGET = 500
STAFF_AGGREGATE_SAMPLE_LIMIT = 500


def _parse_iso_utc(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class TicketNotFoundError(LookupError):
    pass


class TicketSubmissionInProgressError(RuntimeError):
    """Same Idempotency-Key is claimed but not yet completed (issue #258)."""


class DuplicateMergeError(ValueError):
    pass


class StaffScopeForbiddenError(PermissionError):
    pass


class PublicContentUpdateError(ValueError):
    pass


class AiProcessingClaimLostError(RuntimeError):
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
        client_submission_key: str | None = None,
    ) -> SubmitTicketResponse:
        from app.services.complaints.ticket_submission_idempotency import (
            composite_submission_key,
            get_ticket_submission_idempotency_store,
            normalize_client_submission_key,
        )

        # Prefer explicit key (header/body already merged by the route); optional body field.
        raw_key = client_submission_key or payload.client_submission_id
        client_key = normalize_client_submission_key(raw_key)
        composite_key: str | None = None
        idem_store = None
        if client_key:
            idem_store = get_ticket_submission_idempotency_store()
            composite_key = composite_submission_key(
                owner_user_id=owner_user_id,
                client_key=client_key,
            )
            existing = idem_store.get_completed(composite_key)
            if existing is not None:
                return existing
            recovered = self._recover_idempotent_submission(
                composite_key,
                idem_store=idem_store,
                owner_user_id=owner_user_id,
            )
            if recovered is not None:
                return recovered
            if not idem_store.try_begin(composite_key):
                existing = idem_store.get_completed(composite_key)
                if existing is not None:
                    return existing
                recovered = self._recover_idempotent_submission(
                    composite_key,
                    idem_store=idem_store,
                    owner_user_id=owner_user_id,
                )
                if recovered is not None:
                    return recovered
                raise TicketSubmissionInProgressError(
                    "A submission with this idempotency key is already in progress. "
                    "Please wait a moment and retry."
                )

        ticket_persisted = False

        def _mark_ticket_persisted() -> None:
            nonlocal ticket_persisted
            ticket_persisted = True

        try:
            return self._create_submitted_ticket(
                payload,
                owner_user_id=owner_user_id,
                contact=contact,
                composite_key=composite_key,
                idem_store=idem_store,
                on_ticket_persisted=_mark_ticket_persisted,
            )
        except Exception:
            if composite_key and idem_store is not None and not ticket_persisted:
                force_release = getattr(idem_store, "force_release", None)
                if callable(force_release):
                    force_release(composite_key)
                else:
                    idem_store.release(composite_key)
            raise

    def _recover_idempotent_submission(
        self,
        composite_key: str,
        *,
        idem_store: object,
        owner_user_id: str,
    ) -> SubmitTicketResponse | None:
        """Replay a prior create after crash/complete failure using bound ticket id."""
        try_recover = getattr(idem_store, "try_recover", None)
        if callable(try_recover):
            recovered = try_recover(composite_key)
            if recovered is not None:
                return recovered

        get_pending = getattr(idem_store, "get_pending_ticket_id", None)
        if not callable(get_pending):
            return None
        pending_ticket_id = get_pending(composite_key)
        if not pending_ticket_id:
            return None

        ticket = self._store.get(pending_ticket_id)
        if ticket is None:
            return None
        if ticket.owner_user_id and ticket.owner_user_id != owner_user_id:
            return None

        response = SubmitTicketResponse(
            ticketId=ticket.ticket_id,
            ticketNumber=ticket.ticket_number,
            trackingCode=ticket.tracking_code,
            status="SUBMITTED",
            message="Your report was submitted successfully.",
            createdAt=ticket.created_at,
        )
        complete = getattr(idem_store, "complete", None)
        if callable(complete):
            complete(composite_key, response)
        return response

    def _create_submitted_ticket(
        self,
        payload: SubmitTicketRequest,
        *,
        owner_user_id: str,
        contact: ReportContact,
        composite_key: str | None,
        idem_store: object | None,
        on_ticket_persisted=None,
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
        response = SubmitTicketResponse(
            ticketId=ticket_id,
            ticketNumber=ticket_number,
            trackingCode=tracking_code,
            status="SUBMITTED",
            message="Your report was submitted successfully.",
            createdAt=created_at_iso,
        )

        # Bind ticket identity before save so a crash after save / before complete
        # remains recoverable via pendingTicketId + ticket load.
        if composite_key and idem_store is not None:
            bind = getattr(idem_store, "bind_ticket", None)
            if callable(bind):
                bind(composite_key, ticket_id=ticket_id)

        photo_claimed = photo_upload_service.claim_for_ticket(
            payload.image_object_key,
            owner_user_id=owner_user_id,
            ticket_id=ticket_id,
        )
        try:
            self._store.save(stored_ticket)
        except Exception:
            if photo_claimed:
                photo_upload_service.rollback_ticket_claim(
                    payload.image_object_key,
                    owner_user_id=owner_user_id,
                    ticket_id=ticket_id,
                )
            if composite_key and idem_store is not None:
                force_release = getattr(idem_store, "force_release", None)
                if callable(force_release):
                    force_release(composite_key)
            raise

        if callable(on_ticket_persisted):
            on_ticket_persisted()

        # Complete immediately after durable ticket write — before side effects —
        # so retries always replay instead of re-creating.
        if composite_key and idem_store is not None:
            complete = getattr(idem_store, "complete", None)
            if callable(complete):
                complete(composite_key, response)

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

        return response

    def process_ticket_ai(self, ticket_id: str, *, claim_token: str | None = None) -> bool:
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
            active_claim_token = claim_token or uuid4().hex
            ticket = self._store.claim_ai_processing(ticket_id, claimed_at, active_claim_token)
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
                claim_token=active_claim_token,
            )
            if processing_failed:
                logger.warning(
                    "AI processing produced no output for ticket %s.",
                    ticket_id,
                )
                emit_metric("AiProcessingFailed", dimensions={"outcome": "no_output"})
            elif not (classification_ok and cleaning_ok):
                logger.warning(
                    "AI processing partially succeeded for ticket %s "
                    "(classification_ok=%s, cleaning_ok=%s).",
                    ticket_id,
                    classification_ok,
                    cleaning_ok,
                )
                emit_metric(
                    "AiProcessingSucceeded",
                    dimensions={"outcome": "partial"},
                )
            else:
                emit_metric(
                    "AiProcessingSucceeded",
                    dimensions={"outcome": "completed"},
                )
            return True
        except AiProcessingClaimLostError:
            logger.info("AI processing claim was superseded ticket_id=%s", ticket_id)
            return False
        except Exception as exc:
            logger.error(
                "AI processing failed for ticket %s (%s).",
                ticket_id,
                type(exc).__name__,
            )
            emit_metric(
                "AiProcessingFailed",
                dimensions={"outcome": "exception", "error": type(exc).__name__},
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
                    claim_token=active_claim_token,
                )
            except Exception as persistence_exc:
                logger.error(
                    "Could not persist failed AI status for ticket %s (%s).",
                    ticket_id,
                    type(persistence_exc).__name__,
                )
                emit_metric(
                    "DynamoDbErrors",
                    dimensions={"operation": "persist_ai_failure"},
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
        # Publish queue depth for CloudWatch (DynamoDB-safe: uses the recovery scan
        # already performed above, not a separate health-time table scan).
        emit_metric(
            "AiQueuePending",
            value=float(len(recoverable_ids)),
            unit="Count",
            dimensions={"source": "startup_recovery"},
        )
        if len(recoverable_ids) > 0:
            emit_metric(
                "AiQueueBacklog",
                value=float(len(recoverable_ids)),
                unit="Count",
                dimensions={"source": "startup_recovery"},
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

    def list_tickets_page(
        self,
        filters: TicketListFilters | None = None,
        *,
        staff_principal: StaffPrincipal,
        limit: int = STAFF_TICKET_DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> TicketListPageResponse:
        page_size = min(max(limit, 1), STAFF_TICKET_MAX_LIMIT)
        browse_mode, municipality_id, department_ids = _staff_browse_scope(staff_principal)
        store_filters = filters
        sla_state = None if store_filters is None else store_filters.sla_state

        collected: list[StoredTicket] = []
        scanned_count = 0
        current_cursor = cursor
        next_cursor: str | None = None
        # Derived SLA filters need continuation across source pages so a page of
        # non-matching tickets cannot hide later overdue/on-track matches.
        max_rounds = STAFF_SLA_FILTER_MAX_ROUNDS if sla_state is not None else 1

        for _ in range(max_rounds):
            page = self._store.list_staff_page(
                browse_mode=browse_mode,
                municipality_id=municipality_id,
                department_ids=department_ids,
                limit=page_size,
                cursor=current_cursor,
                status=None if store_filters is None else store_filters.status,
                category=None if store_filters is None else store_filters.category,
                urgency=None if store_filters is None else store_filters.urgency,
                department_id=None if store_filters is None else store_filters.department_id,
                assignment_state=None if store_filters is None else store_filters.assignment_state,
                q=None if store_filters is None else store_filters.q,
                open_only=False if store_filters is None else store_filters.open_only,
            )
            scanned_count += page.scanned_count
            page_items = page.items

            if sla_state is None:
                collected.extend(page_items)
                next_cursor = page.next_cursor
                break

            page_filled = False
            for index, ticket in enumerate(page_items):
                if not ticket_matches_filters(
                    ticket,
                    TicketListFilters(sla_state=sla_state),
                ):
                    continue
                collected.append(ticket)
                if len(collected) < page_size:
                    continue
                # Continue after the last included ticket so remaining matches
                # on this source page are not skipped.
                remaining = page_items[index + 1 :]
                if remaining or page.next_cursor:
                    next_cursor = self._store.staff_continuation_cursor(
                        ticket,
                        browse_mode=browse_mode,
                        municipality_id=municipality_id,
                        department_id=(
                            None if store_filters is None else store_filters.department_id
                        ),
                    )
                else:
                    next_cursor = None
                page_filled = True
                break

            if page_filled:
                break
            next_cursor = page.next_cursor
            if not page.next_cursor:
                break
            current_cursor = page.next_cursor

        return TicketListPageResponse(
            items=[map_ticket_to_list_item(ticket) for ticket in collected[:page_size]],
            nextCursor=next_cursor,
            # Dynamo ExclusiveStartKey cursors are forward-only; the admin client
            # keeps a cursor history stack for Previous navigation.
            previousCursor=None,
            limit=page_size,
            scannedCount=scanned_count,
            approximateTotal=None,
            freshnessHintSeconds=30,
        )

    def list_tickets(
        self,
        filters: TicketListFilters | None = None,
        *,
        staff_principal: StaffPrincipal | None = None,
    ):
        """Deprecated wrapper — returns lightweight page items for internal callers."""
        if staff_principal is None:
            raise ValueError("staff_principal is required for list_tickets.")
        return self.list_tickets_page(
            filters,
            staff_principal=staff_principal,
            limit=STAFF_TICKET_MAX_LIMIT,
            cursor=None,
        ).items

    def map_viewport(
        self,
        *,
        staff_principal: StaffPrincipal,
        north: float,
        south: float,
        east: float,
        west: float,
        zoom: float,
        filters: TicketListFilters | None = None,
        limit: int = STAFF_MAP_DEFAULT_LIMIT,
    ) -> TicketMapViewportResponse:
        result_limit = min(max(limit, 1), STAFF_MAP_MAX_LIMIT)
        browse_mode, municipality_id, department_ids = _staff_browse_scope(staff_principal)
        candidates = self._collect_staff_candidates(
            browse_mode=browse_mode,
            municipality_id=municipality_id,
            department_ids=department_ids,
            filters=filters,
            budget=STAFF_MAP_CANDIDATE_BUDGET,
        )
        in_bounds = [
            ticket
            for ticket in candidates
            if _location_in_bounds(
                ticket.location.latitude,
                ticket.location.longitude,
                north=north,
                south=south,
                east=east,
                west=west,
            )
        ]
        truncated = len(candidates) >= STAFF_MAP_CANDIDATE_BUDGET
        use_clusters = zoom < STAFF_MAP_MARKER_ZOOM or len(in_bounds) > result_limit
        if use_clusters:
            clusters = _grid_clusters(in_bounds, zoom=zoom, limit=result_limit)
            return TicketMapViewportResponse(
                markers=[],
                clusters=clusters,
                limit=result_limit,
                truncated=truncated or len(in_bounds) > result_limit,
                zoom=zoom,
            )

        markers = [
            TicketMapMarkerResponse(
                ticketId=ticket.ticket_id,
                ticketNumber=ticket.ticket_number,
                status=ticket.status,
                priority=ticket.priority,
                latitude=ticket.location.latitude,
                longitude=ticket.location.longitude,
                category=ticket.final_category or ticket.category,
            )
            for ticket in in_bounds[:result_limit]
        ]
        return TicketMapViewportResponse(
            markers=markers,
            clusters=[],
            limit=result_limit,
            truncated=truncated or len(in_bounds) > result_limit,
            zoom=zoom,
        )

    def ticket_aggregates(self, staff_principal: StaffPrincipal) -> TicketAggregatesResponse:
        browse_mode, municipality_id, department_ids = _staff_browse_scope(staff_principal)
        tickets, approximate = self._collect_staff_candidates_with_approx(
            browse_mode=browse_mode,
            municipality_id=municipality_id,
            department_ids=department_ids,
            filters=None,
            budget=STAFF_AGGREGATE_SAMPLE_LIMIT,
        )
        open_count = 0
        critical_count = 0
        high_count = 0
        unassigned_count = 0
        overdue_count = 0
        for ticket in tickets:
            if ticket.status in OPEN_TICKET_STATUSES:
                open_count += 1
            if ticket.priority == "critical":
                critical_count += 1
            elif ticket.priority == "high":
                high_count += 1
            if ticket.department_id is None:
                unassigned_count += 1
            if derive_ticket_sla(ticket).state == "overdue":
                overdue_count += 1
        return TicketAggregatesResponse(
            openCount=open_count,
            criticalCount=critical_count,
            highCount=high_count,
            unassignedCount=unassigned_count,
            overdueCount=overdue_count,
            approximate=approximate,
        )

    def _collect_staff_candidates(
        self,
        *,
        browse_mode,
        municipality_id: str | None,
        department_ids: list[str] | None,
        filters: TicketListFilters | None,
        budget: int,
    ) -> list[StoredTicket]:
        tickets, _ = self._collect_staff_candidates_with_approx(
            browse_mode=browse_mode,
            municipality_id=municipality_id,
            department_ids=department_ids,
            filters=filters,
            budget=budget,
        )
        return tickets

    def _collect_staff_candidates_with_approx(
        self,
        *,
        browse_mode,
        municipality_id: str | None,
        department_ids: list[str] | None,
        filters: TicketListFilters | None,
        budget: int,
    ) -> tuple[list[StoredTicket], bool]:
        collected: list[StoredTicket] = []
        cursor: str | None = None
        while len(collected) < budget:
            page_limit = min(100, budget - len(collected))
            page = self._store.list_staff_page(
                browse_mode=browse_mode,
                municipality_id=municipality_id,
                department_ids=department_ids,
                limit=page_limit,
                cursor=cursor,
                status=None if filters is None else filters.status,
                category=None if filters is None else filters.category,
                urgency=None if filters is None else filters.urgency,
                department_id=None if filters is None else filters.department_id,
            )
            items = page.items
            if filters is not None and filters.sla_state is not None:
                items = [
                    ticket
                    for ticket in items
                    if ticket_matches_filters(
                        ticket,
                        TicketListFilters(sla_state=filters.sla_state),
                    )
                ]
            collected.extend(items)
            if not page.next_cursor:
                return collected, False
            cursor = page.next_cursor
        return collected[:budget], True

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
        *,
        claim_token: str | None = None,
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
        if claim_token is not None:
            updated_ticket = self._store.patch_ai_fields(ticket_id, claim_token, update_fields)
            if updated_ticket is None:
                raise AiProcessingClaimLostError(ticket_id)
        else:
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


def _staff_browse_scope(
    principal: StaffPrincipal,
) -> tuple[Literal["admin", "municipality"], str | None, list[str] | None]:
    if principal.role == "administrator":
        return "admin", None, None
    return (
        "municipality",
        principal.municipality_id,
        None if principal.department_ids is None else list(principal.department_ids),
    )


def _location_in_bounds(
    latitude: float,
    longitude: float,
    *,
    north: float,
    south: float,
    east: float,
    west: float,
) -> bool:
    if latitude > north or latitude < south:
        return False
    if west <= east:
        return west <= longitude <= east
    # Viewport crosses the antimeridian.
    return longitude >= west or longitude <= east


def _grid_clusters(
    tickets: list[StoredTicket],
    *,
    zoom: float,
    limit: int,
) -> list[TicketMapClusterResponse]:
    cell = max(0.002, 45.0 / (2 ** max(zoom, 1.0)))
    buckets: dict[tuple[int, int], list[StoredTicket]] = {}
    for ticket in tickets:
        key = (
            int(ticket.location.latitude // cell),
            int(ticket.location.longitude // cell),
        )
        buckets.setdefault(key, []).append(ticket)

    clusters: list[TicketMapClusterResponse] = []
    for (lat_idx, lng_idx), members in sorted(
        buckets.items(),
        key=lambda item: (-len(item[1]), item[0][0], item[0][1]),
    ):
        if len(clusters) >= limit:
            break
        avg_lat = sum(member.location.latitude for member in members) / len(members)
        avg_lng = sum(member.location.longitude for member in members) / len(members)
        clusters.append(
            TicketMapClusterResponse(
                id=f"c-{lat_idx}-{lng_idx}",
                latitude=avg_lat,
                longitude=avg_lng,
                count=len(members),
            )
        )
    return clusters


ticket_service = TicketService(get_ticket_store(), get_status_history_store())
