"""MVP urgency scoring for municipal ticket prioritization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from app.schemas.ticket import ReportLocation
from app.schemas.ticket_status import TicketStatus

UrgencyLevel = Literal["low", "medium", "high", "critical"]

OPEN_STATUSES: frozenset[TicketStatus] = frozenset(
    {"SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS"}
)


@dataclass(frozen=True)
class UrgencyFactorScores:
    safety: int
    location: int
    duplicates: int
    time_open: int
    evidence: int

    def as_dict(self) -> dict[str, int]:
        return {
            "safety": self.safety,
            "location": self.location,
            "duplicates": self.duplicates,
            "timeOpen": self.time_open,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class UrgencyScoreResult:
    urgency_score: int
    urgency_level: UrgencyLevel
    urgency_reason: str
    factor_scores: UrgencyFactorScores

    def as_dict(self) -> dict[str, object]:
        return {
            "urgencyScore": self.urgency_score,
            "urgencyLevel": self.urgency_level,
            "urgencyReason": self.urgency_reason,
            "factorScores": self.factor_scores.as_dict(),
        }


def score_urgency(
    *,
    category: str | None,
    description: str | None,
    location: ReportLocation | None = None,
    created_at: str | None = None,
    status: TicketStatus | None = None,
    duplicate_count: int | None = None,
    has_photo: bool = False,
    now: datetime | None = None,
) -> UrgencyScoreResult:
    """Return the numeric urgency score, level, and staff-facing reason."""

    text = _normalize_text(description)
    resolved_category = category or "PENDING_CLASSIFICATION"
    safety = _score_safety(resolved_category, text)
    location_score = _score_location(text, location)
    duplicates = _score_duplicates(duplicate_count)
    time_open = _score_time_open(created_at, status, now=now)
    evidence = _score_evidence(text, location, has_photo, duplicate_count)

    raw_score = safety + location_score + duplicates + time_open + evidence
    score = min(100, raw_score)

    if safety == 40:
        score = max(score, 75)
    if safety >= 25 and location_score == 20:
        score = max(score, 50)

    level = _level_for_score(score)
    reason = _build_reason(
        level=level,
        score=score,
        safety=safety,
        location_score=location_score,
        duplicate_count=duplicate_count,
        time_open=time_open,
        evidence=evidence,
        location=location,
        text=text,
    )

    return UrgencyScoreResult(
        urgency_score=score,
        urgency_level=level,
        urgency_reason=reason,
        factor_scores=UrgencyFactorScores(
            safety=safety,
            location=location_score,
            duplicates=duplicates,
            time_open=time_open,
            evidence=evidence,
        ),
    )


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def _score_safety(category: str, text: str) -> int:
    if _contains_any(
        text,
        (
            "exposed wire",
            "exposed electrical",
            "live wire",
            "electrocution",
            "fire risk",
            "open trench",
            "collapsed sidewalk",
            "collapsed road",
            "deep open",
        ),
    ):
        return 40

    if category == "traffic_signal":
        if _contains_any(text, ("fully dark", "failed", "not working", "busy intersection")):
            return 40
        return 25

    if category == "road_damage":
        if _contains_any(text, ("deep", "large", "travel lane", "cars swerve", "major road")):
            return 25
        return 10

    if category in {"sidewalk_damage", "water_leak", "drainage"}:
        if _contains_any(text, ("flood", "blocked", "broken", "deep", "hospital", "slip")):
            return 25
        return 10

    if category == "street_lighting":
        if _contains_any(text, ("major", "busy", "pedestrian corridor", "school")):
            return 25
        return 10

    if category == "waste":
        if _contains_any(text, ("biohazard", "sewage", "medical waste", "public-health")):
            return 25
        if _contains_any(text, ("overflowing", "odor", "smell", "garbage bags", "piled")):
            return 10
        return 0

    if category == "public_facilities":
        if _contains_any(text, ("broken", "damaged", "playground", "injury", "sharp")):
            return 25
        return 0

    if category == "PENDING_CLASSIFICATION":
        if _contains_any(text, ("exposed", "electrical", "traffic light", "trench")):
            return 40
        return 10

    return 0


def _score_location(text: str, location: ReportLocation | None) -> int:
    location_text = f"{text} {_normalize_text(location.address_text if location else None)}"
    if _contains_any(
        location_text,
        (
            "school",
            "hospital",
            "clinic",
            "aub",
            "university entrance",
            "university gate",
            "major arterial",
            "ring road",
            "transit hub",
            "busy signalized intersection",
            "critical junction",
        ),
    ):
        return 20
    if _contains_any(
        location_text,
        (
            "busy",
            "hamra",
            "verdun",
            "corniche",
            "downtown",
            "commercial",
            "public road",
            "sidewalk",
        ),
    ):
        return 10
    return 0


def _score_duplicates(duplicate_count: int | None) -> int:
    if duplicate_count is None or duplicate_count <= 0:
        return 0
    if duplicate_count <= 2:
        return 5
    if duplicate_count <= 5:
        return 10
    return 15


def _score_time_open(
    created_at: str | None,
    status: TicketStatus | None,
    *,
    now: datetime | None,
) -> int:
    if not created_at or status not in OPEN_STATUSES:
        return 0

    created = _parse_datetime(created_at)
    if created is None:
        return 0

    reference = now or datetime.now(UTC)
    age_days = (reference - created.astimezone(UTC)).total_seconds() / 86400
    if age_days < 1:
        return 0
    if age_days <= 3:
        return 5
    if age_days <= 7:
        return 10
    return 15


def _score_evidence(
    text: str,
    location: ReportLocation | None,
    has_photo: bool,
    duplicate_count: int | None,
) -> int:
    has_clear_description = len(text) >= 35 and not _contains_any(
        text,
        ("near my house", "not sure"),
    )
    has_precise_location = location is not None and bool(location.address_text.strip())
    has_duplicates = duplicate_count is not None and duplicate_count > 0

    if has_clear_description and has_precise_location and has_photo:
        return 10 if has_duplicates else 7
    if has_clear_description or has_precise_location:
        return 4
    return 0


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _level_for_score(score: int) -> UrgencyLevel:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def _build_reason(
    *,
    level: UrgencyLevel,
    score: int,
    safety: int,
    location_score: int,
    duplicate_count: int | None,
    time_open: int,
    evidence: int,
    location: ReportLocation | None,
    text: str,
) -> str:
    parts = [_safety_reason(safety)]
    if location_score == 20:
        parts.append("critical location")
    elif location_score == 10:
        parts.append("busy public location")
    elif location is None:
        parts.append("location sensitivity uncertain")

    if duplicate_count is None:
        parts.append("duplicates unavailable")
    elif duplicate_count > 0:
        suffix = "s" if duplicate_count != 1 else ""
        parts.append(f"{duplicate_count} nearby open duplicate{suffix}")

    if time_open:
        parts.append(_time_reason(time_open))
    if evidence >= 7:
        parts.append("strong evidence")
    elif evidence == 0:
        parts.append("weak evidence")
    if _contains_any(text, ("police", "ambulance", "fire department", "civil defense")):
        parts.append("not an emergency channel")

    return f"{level.title()} ({score}): {'; '.join(parts)}."


def _safety_reason(score: int) -> str:
    if score == 40:
        return "immediate safety danger"
    if score == 25:
        return "possible injury or collision risk"
    if score == 10:
        return "public disruption or inconvenience"
    return "no clear safety risk"


def _time_reason(score: int) -> str:
    if score == 15:
        return "open over 7 days"
    if score == 10:
        return "open 4-7 days"
    return "open 1-3 days"


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)
