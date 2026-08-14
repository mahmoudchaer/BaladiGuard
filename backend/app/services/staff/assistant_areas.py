"""Deterministic coordinate-cell grouping for repeated-problem summaries (#43)."""

from __future__ import annotations

import math
from collections import Counter, defaultdict

from app.schemas.staff_assistant import StaffAssistantAreaCluster
from app.schemas.stored_ticket import StoredTicket

# 0.002 degrees is about 220m of latitude and a similar east-west span in Lebanon.
# Cells are closed on the south/west edges and open on the north/east edges.
CELL_SIZE_DEGREES = 0.002
UNLOCATED_CELL_ID = "unlocated"
MINIMUM_DISTINCT_REPORTS = 2
MAX_AREA_CLUSTERS = 20
MAX_CLUSTER_TICKET_IDS = 20


def has_usable_coordinates(ticket: StoredTicket) -> bool:
    if ticket.location.source == "PLACEHOLDER":
        return False
    return math.isfinite(ticket.location.latitude) and math.isfinite(ticket.location.longitude)


def cell_origin(value: float) -> float:
    return math.floor((value / CELL_SIZE_DEGREES) + 1e-12) * CELL_SIZE_DEGREES


def cell_id_for(ticket: StoredTicket) -> str:
    if not has_usable_coordinates(ticket):
        return UNLOCATED_CELL_ID
    south = cell_origin(ticket.location.latitude)
    west = cell_origin(ticket.location.longitude)
    return f"{south:.3f},{west:.3f}"


def cell_bounds(cell_id: str) -> tuple[float, float, float, float] | None:
    if cell_id == UNLOCATED_CELL_ID:
        return None
    south_text, west_text = cell_id.split(",", maxsplit=1)
    south = float(south_text)
    west = float(west_text)
    return south, west, south + CELL_SIZE_DEGREES, west + CELL_SIZE_DEGREES


def distinct_report_key(ticket: StoredTicket) -> str:
    if ticket.duplicate_group_id:
        return f"group:{ticket.duplicate_group_id}"
    return f"ticket:{ticket.ticket_id}"


def choose_safe_label(cell_id: str, tickets: list[StoredTicket]) -> str:
    labels = Counter(
        (ticket.public_location_label or "").strip()
        for ticket in tickets
        if (ticket.public_location_label or "").strip()
    )
    if labels:
        return min(labels, key=lambda label: (-labels[label], label.casefold(), label))
    if cell_id == UNLOCATED_CELL_ID:
        return "Unlocated reports"
    return f"Unlabeled cell {cell_id}"


def _category(ticket: StoredTicket) -> str:
    return ticket.final_category or ticket.category


def build_area_clusters(
    tickets: list[StoredTicket],
) -> tuple[list[StaffAssistantAreaCluster], list[StoredTicket], int]:
    grouped: dict[str, list[StoredTicket]] = defaultdict(list)
    for ticket in tickets:
        grouped[cell_id_for(ticket)].append(ticket)

    clusters: list[StaffAssistantAreaCluster] = []
    members_by_cell: dict[str, list[StoredTicket]] = {}
    for cell_id, members in grouped.items():
        distinct_keys = {distinct_report_key(ticket) for ticket in members}
        if cell_id == UNLOCATED_CELL_ID or len(distinct_keys) < MINIMUM_DISTINCT_REPORTS:
            continue
        grouped_ids = {ticket.duplicate_group_id for ticket in members if ticket.duplicate_group_id}
        separate = [ticket for ticket in members if not ticket.duplicate_group_id]
        bounds = cell_bounds(cell_id)
        south, west, north, east = bounds if bounds else (None, None, None, None)
        categories = dict(sorted(Counter(_category(ticket) for ticket in members).items()))
        ticket_ids = sorted(ticket.ticket_id for ticket in members)
        clusters.append(
            StaffAssistantAreaCluster(
                cellId=cell_id,
                south=south,
                west=west,
                north=north,
                east=east,
                label=choose_safe_label(cell_id, members),
                ticketCount=len(members),
                distinctReportCount=len(distinct_keys),
                duplicateGroupCount=len(grouped_ids),
                separateReportCount=len(separate),
                categories=categories,
                ticketIds=ticket_ids[:MAX_CLUSTER_TICKET_IDS],
                ticketIdsTruncated=len(ticket_ids) > MAX_CLUSTER_TICKET_IDS,
            )
        )
        members_by_cell[cell_id] = members
    clusters.sort(key=lambda item: (-item.distinct_report_count, item.cell_id))
    shown = clusters[:MAX_AREA_CLUSTERS]
    selected = [ticket for cluster in clusters for ticket in members_by_cell[cluster.cell_id]]
    return shown, selected, len(clusters)
