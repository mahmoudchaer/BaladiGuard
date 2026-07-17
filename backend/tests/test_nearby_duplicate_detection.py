"""Tests for nearby duplicate detection (issue #25)."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings
from app.schemas.stored_ticket import PENDING_CLASSIFICATION, StoredTicket
from app.schemas.ticket import ReportContact, ReportLocation
from app.services.duplicates import find_nearby_duplicates, haversine_meters
from app.services.duplicates.category_similarity import category_match_type

REPO_ROOT = Path(__file__).resolve().parents[2]
MOCK_TICKETS_PATH = REPO_ROOT / "mock_tickets.json"


def _ticket(
    *,
    ticket_id: str,
    category: str,
    latitude: float,
    longitude: float,
    status: str = "SUBMITTED",
    final_category: str | None = None,
) -> StoredTicket:
    return StoredTicket(
        ticketId=ticket_id,
        ticketNumber=f"BG-{ticket_id[-4:]}",
        trackingCode=ticket_id[-6:].upper(),
        description="Sample municipal report.",
        contact=ReportContact(name="Test User", phone="+96170000000"),
        location=ReportLocation(
            latitude=latitude,
            longitude=longitude,
            addressText="Beirut",
            source="GPS",
        ),
        imageObjectKey=f"reports/mock/{ticket_id}.jpg",
        status=status,  # type: ignore[arg-type]
        category=category,
        finalCategory=final_category,
        createdAt="2026-07-18T00:00:00Z",
        updatedAt="2026-07-18T00:00:00Z",
    )


def _load_mock_tickets() -> list[StoredTicket]:
    raw = json.loads(MOCK_TICKETS_PATH.read_text(encoding="utf-8"))
    return [StoredTicket.model_validate(item) for item in raw]


def test_haversine_distance_for_hamra_waste_pair_is_a_few_meters() -> None:
    distance = haversine_meters(33.893791, 35.501777, 33.89382, 35.5018)
    assert 1.0 < distance < 10.0


def test_find_nearby_duplicates_matches_mock_waste_pair() -> None:
    tickets = _load_mock_tickets()
    query = next(ticket for ticket in tickets if ticket.ticket_number == "BG-2026-0005")

    result = find_nearby_duplicates(
        category=query.category,
        latitude=query.location.latitude,
        longitude=query.location.longitude,
        tickets=tickets,
        exclude_ticket_id=query.ticket_id,
    )

    assert result.distance_threshold_meters == get_settings().duplicate_distance_threshold_m
    assert any(match.ticket_id.endswith("222222222222222222222222") for match in result.matches)
    waste_match = next(
        match for match in result.matches if match.ticket_id.endswith("222222222222222222222222")
    )
    assert waste_match.category == "waste"
    assert waste_match.category_match == "same"
    assert waste_match.status == "IN_PROGRESS"
    assert waste_match.distance_meters < 10
    assert waste_match.score >= get_settings().duplicate_min_score


def test_find_nearby_duplicates_excludes_resolved_tickets() -> None:
    tickets = [
        _ticket(
            ticket_id="tkt_open_waste",
            category="waste",
            latitude=33.8938,
            longitude=35.5018,
            status="SUBMITTED",
        ),
        _ticket(
            ticket_id="tkt_resolved_waste",
            category="waste",
            latitude=33.89381,
            longitude=35.50181,
            status="RESOLVED",
        ),
    ]

    result = find_nearby_duplicates(
        category="waste",
        latitude=33.8938,
        longitude=35.5018,
        tickets=tickets,
        exclude_ticket_id="tkt_open_waste",
    )

    assert [match.ticket_id for match in result.matches] == []


def test_find_nearby_duplicates_includes_similar_road_and_sidewalk_categories() -> None:
    tickets = [
        _ticket(
            ticket_id="tkt_sidewalk",
            category="sidewalk_damage",
            latitude=33.9000,
            longitude=35.5000,
            status="UNDER_REVIEW",
        ),
        _ticket(
            ticket_id="tkt_waste_elsewhere",
            category="waste",
            latitude=33.90005,
            longitude=35.50005,
            status="SUBMITTED",
        ),
    ]

    result = find_nearby_duplicates(
        category="road_damage",
        latitude=33.9000,
        longitude=35.5000,
        tickets=tickets,
    )

    assert len(result.matches) == 1
    assert result.matches[0].ticket_id == "tkt_sidewalk"
    assert result.matches[0].category_match == "similar"
    assert result.matches[0].category == "sidewalk_damage"


def test_find_nearby_duplicates_respects_distance_threshold_override() -> None:
    tickets = [
        _ticket(
            ticket_id="tkt_far_waste",
            category="waste",
            latitude=33.9000,
            longitude=35.5100,
            status="SUBMITTED",
        ),
    ]

    within = find_nearby_duplicates(
        category="waste",
        latitude=33.9000,
        longitude=35.5000,
        tickets=tickets,
        distance_threshold_meters=2000,
        min_score=0.0,
    )
    outside = find_nearby_duplicates(
        category="waste",
        latitude=33.9000,
        longitude=35.5000,
        tickets=tickets,
        distance_threshold_meters=50,
        min_score=0.0,
    )

    assert len(within.matches) == 1
    assert within.matches[0].distance_meters > 50
    assert outside.matches == []


def test_find_nearby_duplicates_uses_final_category_when_present() -> None:
    tickets = [
        _ticket(
            ticket_id="tkt_reviewed",
            category=PENDING_CLASSIFICATION,
            final_category="waste",
            latitude=33.8938,
            longitude=35.5018,
            status="ASSIGNED",
        ),
    ]

    result = find_nearby_duplicates(
        category="waste",
        latitude=33.8938,
        longitude=35.5018,
        tickets=tickets,
    )

    assert len(result.matches) == 1
    assert result.matches[0].category == "waste"
    assert result.matches[0].category_match == "same"


def test_find_nearby_duplicates_returns_empty_when_no_neighbors() -> None:
    result = find_nearby_duplicates(
        category="noise",
        latitude=33.8800,
        longitude=35.4800,
        tickets=[],
    )
    assert result.matches == []


def test_category_match_type_rules() -> None:
    assert category_match_type("waste", "waste") == "same"
    assert category_match_type("road_damage", "sidewalk_damage") == "similar"
    assert category_match_type("waste", "noise") is None
    assert category_match_type(PENDING_CLASSIFICATION, "waste") is None
    assert category_match_type(PENDING_CLASSIFICATION, PENDING_CLASSIFICATION) == "same"
