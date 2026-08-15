"""Bounded, permission-scoped staff global search (issue #42 / #260)."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.core.staff_auth import StaffPrincipal, staff_can_access_ticket
from app.schemas.staff_search import (
    StaffSearchResponse,
    StaffSearchTeamHit,
    StaffSearchTicketHit,
    StaffSearchWorkerHit,
    StaffSearchWorkOrderHit,
)
from app.schemas.stored_ticket import StoredTicket
from app.schemas.work_order import StoredWorkOrder
from app.utils.search_text import normalize_search_query, search_text_contains
from app.utils.ticket_ids import is_valid_tracking_code, normalize_tracking_code

MAX_SEARCH_QUERY_LENGTH = 80
MIN_SEARCH_QUERY_LENGTH = 2
MAX_RESULTS_PER_TYPE = 8
TICKET_SCAN_BUDGET = 200
WORKFORCE_SCAN_BUDGET = 80
WORK_ORDER_QUERY_BUDGET = 40

_TICKET_NUMBER_RE = re.compile(r"^bg-\d{4}-\d+$", re.IGNORECASE)


def _as_of() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _contains(haystack: str | None, needle: str) -> bool:
    return search_text_contains(haystack, needle)


def ticket_matches_approved_text(ticket: StoredTicket, query: str) -> bool:
    """Match only operational identifiers and staff-safe location labels."""

    approved = (
        ticket.ticket_id,
        ticket.ticket_number,
        ticket.tracking_code,
        ticket.public_location_label,
    )
    return any(_contains(part, query) for part in approved)


class StaffSearchService:
    def search(self, query: str, *, principal: StaffPrincipal) -> StaffSearchResponse:
        normalized = normalize_search_query(query)
        tickets: list[StaffSearchTicketHit] = []
        workers: list[StaffSearchWorkerHit] = []
        teams: list[StaffSearchTeamHit] = []
        work_orders: list[StaffSearchWorkOrderHit] = []
        partial_failures: list[str] = []
        scan_truncated = False
        workforce_scan_truncated = False
        work_order_scan_truncated = False
        scanned: list[StoredTicket] = []

        try:
            scanned, scan_truncated = self._scan_tickets(principal)
            tickets = self._search_tickets(normalized, principal, scanned)
        except Exception:
            partial_failures.append("tickets")
            scanned = []

        try:
            work_orders, work_order_scan_truncated = self._search_work_orders(
                normalized, principal, scanned
            )
        except Exception:
            partial_failures.append("work_orders")

        workers_truncated = False
        teams_truncated = False
        try:
            workers, teams, workers_truncated, teams_truncated = self._search_workforce(
                normalized, principal
            )
            workforce_scan_truncated = workers_truncated or teams_truncated
        except Exception:
            partial_failures.append("workforce")

        tickets_truncated = len(tickets) > MAX_RESULTS_PER_TYPE
        work_orders_truncated = len(work_orders) > MAX_RESULTS_PER_TYPE or work_order_scan_truncated
        return StaffSearchResponse(
            asOf=_as_of(),
            query=normalized,
            tickets=tickets[:MAX_RESULTS_PER_TYPE],
            workers=workers[:MAX_RESULTS_PER_TYPE],
            teams=teams[:MAX_RESULTS_PER_TYPE],
            workOrders=work_orders[:MAX_RESULTS_PER_TYPE],
            ticketsTruncated=tickets_truncated,
            workersTruncated=workers_truncated,
            teamsTruncated=teams_truncated,
            workOrdersTruncated=work_orders_truncated,
            scanTruncated=scan_truncated,
            workforceScanTruncated=workforce_scan_truncated,
            workOrderScanTruncated=work_order_scan_truncated,
            partialFailures=partial_failures,
            limits={
                "maxQueryLength": MAX_SEARCH_QUERY_LENGTH,
                "minQueryLength": MIN_SEARCH_QUERY_LENGTH,
                "maxResultsPerType": MAX_RESULTS_PER_TYPE,
                "ticketScanBudget": TICKET_SCAN_BUDGET,
                "workforceScanBudget": WORKFORCE_SCAN_BUDGET,
                "workOrderQueryBudget": WORK_ORDER_QUERY_BUDGET,
            },
        )

    def _scan_tickets(self, principal: StaffPrincipal) -> tuple[list[StoredTicket], bool]:
        from app.services.complaints.ticket_service import ticket_service

        return ticket_service.collect_staff_tickets_bounded(principal, budget=TICKET_SCAN_BUDGET)

    def _search_tickets(
        self,
        query: str,
        principal: StaffPrincipal,
        scanned: list[StoredTicket],
    ) -> list[StaffSearchTicketHit]:
        from app.database.store_factory import get_ticket_store

        store = get_ticket_store()
        by_id: dict[str, StoredTicket] = {}
        ordered_ids: list[str] = []

        def consider(ticket: StoredTicket) -> None:
            if not staff_can_access_ticket(principal, ticket):
                return
            if ticket.ticket_id in by_id:
                return
            by_id[ticket.ticket_id] = ticket
            ordered_ids.append(ticket.ticket_id)

        compact = query.strip()
        tracking_candidate = re.sub(r"\s+", "", compact)
        if compact.startswith("tkt_"):
            loaded = store.get(compact)
            if loaded is not None:
                consider(loaded)
        if is_valid_tracking_code(tracking_candidate):
            loaded = store.get_by_tracking_code(normalize_tracking_code(tracking_candidate))
            if loaded is not None:
                consider(loaded)

        for ticket in scanned:
            if ticket.ticket_id in by_id:
                continue
            if (
                _TICKET_NUMBER_RE.fullmatch(compact)
                and ticket.ticket_number.casefold() == compact.casefold()
            ):
                consider(ticket)
                continue
            if ticket_matches_approved_text(ticket, query):
                consider(ticket)

        return [self._ticket_hit(by_id[ticket_id]) for ticket_id in ordered_ids]

    def _search_work_orders(
        self,
        query: str,
        principal: StaffPrincipal,
        scanned: list[StoredTicket],
    ) -> tuple[list[StaffSearchWorkOrderHit], bool]:
        from app.database.store_factory import get_ticket_store, get_work_order_store

        store = get_work_order_store()
        tickets = get_ticket_store()
        hits: list[StaffSearchWorkOrderHit] = []
        seen: set[str] = set()
        compact = query.strip()
        queries_used = 0
        truncated = False

        if compact.startswith("wo_"):
            loaded = store.get(compact)
            if loaded is not None:
                ticket = tickets.get(loaded.ticket_id)
                if ticket is not None and staff_can_access_ticket(principal, ticket):
                    return [self._work_order_hit(loaded, ticket.ticket_number)], False
                return [], False

        for ticket in scanned:
            if not staff_can_access_ticket(principal, ticket):
                continue
            if queries_used >= WORK_ORDER_QUERY_BUDGET:
                truncated = True
                break
            if len(hits) > MAX_RESULTS_PER_TYPE:
                truncated = True
                break
            queries_used += 1
            for work_order in store.list_by_ticket_id(ticket.ticket_id):
                if work_order.work_order_id in seen:
                    continue
                if not (
                    _contains(work_order.work_order_id, query)
                    or _contains(work_order.summary, query)
                    or _contains(work_order.state, query)
                    or _contains(ticket.ticket_number, query)
                ):
                    continue
                seen.add(work_order.work_order_id)
                hits.append(self._work_order_hit(work_order, ticket.ticket_number))
                if len(hits) > MAX_RESULTS_PER_TYPE:
                    truncated = True
                    break
        return hits, truncated

    def _search_workforce(
        self, query: str, principal: StaffPrincipal
    ) -> tuple[list[StaffSearchWorkerHit], list[StaffSearchTeamHit], bool, bool]:
        from app.services.workforce.service import workforce_service

        workers, workers_truncated = workforce_service.search_workers(
            principal,
            query=query,
            budget=WORKFORCE_SCAN_BUDGET,
            limit=MAX_RESULTS_PER_TYPE,
        )
        teams, teams_truncated = workforce_service.search_teams(
            principal,
            query=query,
            budget=WORKFORCE_SCAN_BUDGET,
            limit=MAX_RESULTS_PER_TYPE,
        )
        worker_hits = [
            StaffSearchWorkerHit(
                workerId=item.worker_id,
                displayName=item.display_name,
                departmentIds=item.department_ids,
                active=item.active,
            )
            for item in workers
        ]
        team_hits = [
            StaffSearchTeamHit(
                teamId=item.team_id,
                displayName=item.display_name,
                departmentIds=item.department_ids,
                active=item.active,
            )
            for item in teams
        ]
        return worker_hits, team_hits, workers_truncated, teams_truncated

    def _ticket_hit(self, ticket: StoredTicket) -> StaffSearchTicketHit:
        label = (ticket.public_location_label or "").strip() or None
        return StaffSearchTicketHit(
            ticketId=ticket.ticket_id,
            ticketNumber=ticket.ticket_number,
            trackingCode=ticket.tracking_code,
            status=ticket.status,
            category=ticket.final_category or ticket.category,
            publicLocationLabel=label,
        )

    def _work_order_hit(
        self, work_order: StoredWorkOrder, ticket_number: str | None
    ) -> StaffSearchWorkOrderHit:
        return StaffSearchWorkOrderHit(
            workOrderId=work_order.work_order_id,
            ticketId=work_order.ticket_id,
            ticketNumber=ticket_number,
            state=work_order.state,
            summary=work_order.summary,
        )


staff_search_service = StaffSearchService()
