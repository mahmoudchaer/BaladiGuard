"""Tests for canonical category → department mapping (issue #31)."""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas.stored_ticket import PENDING_CLASSIFICATION
from app.services.duplicates.category_similarity import category_match_type
from app.services.routing import (
    category_to_department_map,
    department_id_for_category,
    department_ids,
    department_name,
    load_department_catalog,
    suggest_department_id,
)

SEEDS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "db" / "seeds"
CATEGORY_SEED_PATH = SEEDS_DIR / "categories.json"
DEPARTMENT_SEED_PATH = SEEDS_DIR / "departments.json"

EXPECTED_MAP = {
    "road_damage": "d1111111-1111-1111-1111-111111111111",
    "sidewalk_damage": "d1111111-1111-1111-1111-111111111111",
    "waste": "d2222222-2222-2222-2222-222222222222",
    "street_lighting": "d3333333-3333-3333-3333-333333333333",
    "water_leak": "d4444444-4444-4444-4444-444444444444",
    "noise": "d5555555-5555-5555-5555-555555555555",
    "traffic_signal": "d6666666-6666-6666-6666-666666666666",
    "drainage": "d7777777-7777-7777-7777-777777777777",
    "public_facilities": "d8888888-8888-8888-8888-888888888888",
}


def test_every_concrete_category_maps_to_seeded_department() -> None:
    mapping = category_to_department_map()
    seeded_departments = department_ids()

    assert mapping == EXPECTED_MAP
    assert set(mapping.values()) <= seeded_departments


def test_pending_classification_has_no_department() -> None:
    assert department_id_for_category(PENDING_CLASSIFICATION) is None
    assert PENDING_CLASSIFICATION not in category_to_department_map()


def test_shared_department_categories_resolve_to_same_id() -> None:
    road = department_id_for_category("road_damage")
    sidewalk = department_id_for_category("sidewalk_damage")
    assert road is not None
    assert road == sidewalk
    assert category_match_type("road_damage", "sidewalk_damage") == "similar"


def test_seed_files_and_routing_module_stay_consistent() -> None:
    categories = json.loads(CATEGORY_SEED_PATH.read_text(encoding="utf-8"))
    departments = json.loads(DEPARTMENT_SEED_PATH.read_text(encoding="utf-8"))
    seeded_department_ids = {item["departmentId"] for item in departments}

    assert {item["departmentId"] for item in load_department_catalog()} == seeded_department_ids
    assert len(load_department_catalog()) == 8

    for item in categories:
        category_id = item["categoryId"]
        department_id = item.get("departmentId")
        if category_id == PENDING_CLASSIFICATION:
            assert department_id is None
            continue
        assert isinstance(department_id, str)
        assert department_id in seeded_department_ids
        assert department_id_for_category(category_id) == department_id


def test_department_name_lookup() -> None:
    assert department_name("d2222222-2222-2222-2222-222222222222") == "Waste Management"
    assert department_name("missing") is None


def test_department_suggestion_uses_seeded_rules_with_processed_ticket_context() -> None:
    assert (
        suggest_department_id(
            category_id="traffic_signal",
            urgency_level="critical",
            urgency_score=88,
        )
        == "d6666666-6666-6666-6666-666666666666"
    )
    assert suggest_department_id(category_id=PENDING_CLASSIFICATION, urgency_level="high") is None
    assert suggest_department_id(category_id=None, urgency_score=75) is None


def test_ticket_read_mapper_uses_seed_backed_department_name() -> None:
    from app.schemas.stored_ticket import StoredTicket
    from app.schemas.ticket import ReportContact, ReportLocation
    from app.services.complaints.ticket_read_mapper import map_ticket_to_response

    ticket = StoredTicket(
        ticketId="tkt_department_name_lookup_00000000000001",
        ticketNumber="BG-2026-9999",
        trackingCode="DEPT01",
        description="Broken street lamp on the corner.",
        contact=ReportContact(name="Test User", phone="+96170000000"),
        location=ReportLocation(
            latitude=33.896112,
            longitude=35.478419,
            addressText="Beirut",
            source="GPS",
        ),
        imageObjectKey="reports/mock/street-light.jpg",
        status="SUBMITTED",
        category="street_lighting",
        departmentId="d3333333-3333-3333-3333-333333333333",
        createdAt="2026-07-21T00:00:00Z",
        updatedAt="2026-07-21T00:00:00Z",
    )

    response = map_ticket_to_response(ticket)
    assert response.department is not None
    assert response.department.department_id == "d3333333-3333-3333-3333-333333333333"
    assert response.department.name == "Street Lighting"
