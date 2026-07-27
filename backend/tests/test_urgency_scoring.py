from datetime import UTC, datetime

import pytest

from app.schemas.ticket import ReportLocation
from app.services.urgency import score_urgency

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


def location(address: str = "Hamra, Beirut") -> ReportLocation:
    return ReportLocation(
        latitude=33.8938,
        longitude=35.5018,
        addressText=address,
        source="GPS",
    )


@pytest.mark.parametrize(
    ("payload", "expected_score", "expected_level"),
    [
        (
            {
                "category": "road_damage",
                "description": (
                    "Small shallow pothole on a quiet residential side street in Achrafieh."
                ),
                "location": location("Quiet residential side street, Achrafieh"),
                "duplicate_count": 0,
                "created_at": "2026-07-18T06:00:00Z",
                "has_photo": False,
            },
            14,
            "low",
        ),
        (
            {
                "category": "road_damage",
                "description": (
                    "Deep pothole in the travel lane on a busy Beirut arterial; cars swerve."
                ),
                "location": location("Busy Beirut major arterial"),
                "duplicate_count": 1,
                "created_at": "2026-07-16T12:00:00Z",
                "has_photo": True,
            },
            62,
            "high",
        ),
        (
            {
                "category": "traffic_signal",
                "description": "Traffic light fully dark at a busy signalized intersection.",
                "location": location("Busy signalized intersection"),
                "duplicate_count": 2,
                "created_at": "2026-07-18T04:00:00Z",
                "has_photo": True,
            },
            75,
            "critical",
        ),
        (
            {
                "category": "water_leak",
                "description": (
                    "Continuous clean water flooding the sidewalk and curb near a "
                    "hospital entrance."
                ),
                "location": location("Hospital entrance"),
                "duplicate_count": 0,
                "created_at": "2026-07-17T12:00:00Z",
                "has_photo": True,
            },
            57,
            "high",
        ),
        (
            {
                "category": "waste",
                "description": (
                    "Overflowing bins and garbage bags piled on a busy Hamra sidewalk; strong odor."
                ),
                "location": location("Hamra Street, Beirut"),
                "duplicate_count": 4,
                "created_at": "2026-07-13T12:00:00Z",
                "has_photo": True,
            },
            50,
            "high",
        ),
        (
            {
                "category": "street_lighting",
                "description": "Light not working near my house.",
                "location": None,
                "duplicate_count": None,
                "created_at": "2026-07-15T12:00:00Z",
                "has_photo": False,
            },
            15,
            "low",
        ),
        (
            {
                "category": "drainage",
                "description": "Storm drain blocked; street floods whenever it rains.",
                "location": location("Busy public road"),
                "duplicate_count": 2,
                "created_at": "2026-07-09T12:00:00Z",
                "has_photo": False,
            },
            59,
            "high",
        ),
        (
            {
                "category": "public_facilities",
                "description": (
                    "Exposed electrical wires hanging from a damaged public light pole "
                    "beside a school gate."
                ),
                "location": location("School gate"),
                "duplicate_count": 1,
                "created_at": "2026-07-18T08:00:00Z",
                "has_photo": True,
            },
            75,
            "critical",
        ),
    ],
)
def test_score_urgency_matches_documented_examples(payload, expected_score, expected_level):
    result = score_urgency(status="SUBMITTED", now=NOW, **payload)

    assert result.urgency_level == expected_level
    assert result.urgency_score == pytest.approx(expected_score, abs=5)
    assert result.factor_scores.as_dict().keys() == {
        "safety",
        "location",
        "duplicates",
        "timeOpen",
        "evidence",
    }
    assert result.urgency_reason.startswith(f"{expected_level.title()} ({result.urgency_score}):")


@pytest.mark.parametrize(
    ("payload", "required_phrases"),
    [
        (
            {
                "category": "road_damage",
                "description": (
                    "Deep pothole in the travel lane on a busy Beirut arterial; cars swerve."
                ),
                "location": location("Busy Beirut major arterial"),
                "duplicate_count": 1,
                "created_at": "2026-07-16T12:00:00Z",
                "has_photo": True,
            },
            ("possible injury or collision risk", "critical location"),
        ),
        (
            {
                "category": "traffic_signal",
                "description": "Traffic light fully dark at a busy signalized intersection.",
                "location": location("Busy signalized intersection"),
                "duplicate_count": 2,
                "created_at": "2026-07-18T04:00:00Z",
                "has_photo": True,
            },
            ("immediate safety danger", "critical location"),
        ),
        (
            {
                "category": "waste",
                "description": (
                    "Overflowing bins and garbage bags piled on a busy Hamra sidewalk; strong odor."
                ),
                "location": location("Hamra Street, Beirut"),
                "duplicate_count": 4,
                "created_at": "2026-07-13T12:00:00Z",
                "has_photo": True,
            },
            ("4 nearby open duplicates", "busy public location"),
        ),
        (
            {
                "category": "public_facilities",
                "description": (
                    "Exposed electrical wires hanging from a damaged public light pole "
                    "beside a school gate."
                ),
                "location": location("School gate"),
                "duplicate_count": 1,
                "created_at": "2026-07-18T08:00:00Z",
                "has_photo": True,
            },
            ("immediate safety danger", "critical location"),
        ),
    ],
)
def test_urgency_reason_references_strongest_scoring_factors(payload, required_phrases):
    result = score_urgency(status="SUBMITTED", now=NOW, **payload)

    for phrase in required_phrases:
        assert phrase in result.urgency_reason


def test_urgency_reason_orders_factors_by_strength():
    result = score_urgency(
        category="road_damage",
        description="Deep pothole in the travel lane on a busy Beirut arterial; cars swerve.",
        location=location("Busy Beirut major arterial"),
        duplicate_count=1,
        created_at="2026-07-16T12:00:00Z",
        status="SUBMITTED",
        has_photo=True,
        now=NOW,
    )

    # Safety (25) and location (20) outrank corroborated evidence (10) and duplicates (5).
    assert result.urgency_score == 65
    assert result.urgency_reason == (
        "High (65): possible injury or collision risk; critical location; strong evidence."
    )


def test_urgency_reason_includes_emergency_disclaimer_when_needed():
    result = score_urgency(
        category="road_damage",
        description="Deep pothole blocking the road — call the police and ambulance now.",
        location=location("Busy Beirut major arterial"),
        duplicate_count=0,
        created_at="2026-07-18T10:00:00Z",
        status="SUBMITTED",
        has_photo=True,
        now=NOW,
    )

    assert "not an emergency channel" in result.urgency_reason


def test_score_urgency_handles_missing_optional_fields():
    result = score_urgency(
        category=None,
        description=None,
        location=None,
        created_at=None,
        status="SUBMITTED",
        duplicate_count=None,
        has_photo=False,
        now=NOW,
    )

    assert result.urgency_score == 10
    assert result.urgency_level == "low"
    assert "duplicates unavailable" in result.urgency_reason
    assert "location sensitivity uncertain" in result.urgency_reason


def test_score_urgency_handles_arabic_safety_and_location_cues():
    result = score_urgency(
        category="public_facilities",
        description="اسلاك كهرباء مكشوفة قرب بوابة مدرسة في بيروت",
        location=location("بوابة مدرسة"),
        created_at="2026-07-18T08:00:00Z",
        status="SUBMITTED",
        duplicate_count=1,
        has_photo=True,
        now=NOW,
    )

    assert result.urgency_level == "critical"
    assert result.urgency_score >= 75
    assert result.factor_scores.safety == 40
    assert result.factor_scores.location == 20


def test_score_urgency_uses_nearby_known_landmarks_for_generic_gps_labels():
    result = score_urgency(
        category="road_damage",
        description="Deep pothole in the travel lane causing cars to swerve.",
        location=ReportLocation(
            latitude=33.896112,
            longitude=35.478419,
            addressText="Selected map location",
            source="GPS",
        ),
        created_at="2026-07-16T12:00:00Z",
        status="SUBMITTED",
        duplicate_count=1,
        has_photo=True,
        now=NOW,
    )

    assert result.factor_scores.location == 20
    assert result.urgency_level == "high"
