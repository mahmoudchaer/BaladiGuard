"""Versioned, bounded scoring rules for verified civic contribution (issue #323)."""

from __future__ import annotations

import re
from typing import Literal

RULE_VERSION = "rewards-v1"

REASON_MUNICIPALITY_ACCEPTED = "MUNICIPALITY_ACCEPTED"
REASON_IN_PROGRESS = "IN_PROGRESS"
REASON_RESOLVED = "RESOLVED"
REASON_SUPPORTING_EVIDENCE = "SUPPORTING_EVIDENCE"
REASON_SAFETY_CLEARED = "SAFETY_CLEARED"
REASON_REVERSAL_REJECTED = "REVERSAL_REJECTED"
REASON_REVERSAL_REOPENED = "REVERSAL_REOPENED"
REASON_REVERSAL_MERGED = "REVERSAL_MERGED"
REASON_REVERSAL_SAFETY = "REVERSAL_SAFETY"
REASON_REVERSAL_ABUSE = "REVERSAL_ABUSE"
REASON_OPS_CORRECTION = "OPS_CORRECTION"

POINTS: dict[str, int] = {
    REASON_MUNICIPALITY_ACCEPTED: 10,
    REASON_IN_PROGRESS: 8,
    REASON_RESOLVED: 20,
    REASON_SUPPORTING_EVIDENCE: 4,
    REASON_SAFETY_CLEARED: 3,
}

CONFIRMED_PATH_REASONS = (
    REASON_MUNICIPALITY_ACCEPTED,
    REASON_IN_PROGRESS,
    REASON_RESOLVED,
)

PENDING_REASONS = (REASON_SAFETY_CLEARED,)

ABUSE_CONFIRMED_AWARD_LIMIT_24H = 8

LEVELS: tuple[tuple[str, int, str], ...] = (
    ("neighbor", 0, "Neighbor"),
    ("helper", 25, "Helper"),
    ("steward", 50, "Steward"),
    ("guardian", 100, "Guardian"),
    ("champion", 200, "Civic Champion"),
)

CITIZEN_REASON_MAP: dict[str, Literal[
    "accepted",
    "in_progress",
    "resolved",
    "supporting",
    "reviewing",
    "adjusted",
    "adjustment",
]] = {
    REASON_MUNICIPALITY_ACCEPTED: "accepted",
    REASON_IN_PROGRESS: "in_progress",
    REASON_RESOLVED: "resolved",
    REASON_SUPPORTING_EVIDENCE: "supporting",
    REASON_SAFETY_CLEARED: "reviewing",
    REASON_REVERSAL_REJECTED: "adjusted",
    REASON_REVERSAL_REOPENED: "adjusted",
    REASON_REVERSAL_MERGED: "adjusted",
    REASON_REVERSAL_SAFETY: "adjusted",
    REASON_REVERSAL_ABUSE: "adjusted",
    REASON_OPS_CORRECTION: "adjustment",
}

_PHONE_LIKE = re.compile(r"\d{8,}")


def award_event_key(
    *,
    citizen_user_id: str,
    ticket_id: str,
    reason_code: str,
    rule_version: str = RULE_VERSION,
) -> str:
    return f"award:{citizen_user_id}:{ticket_id}:{reason_code}:{rule_version}"


def reversal_event_key(
    *,
    citizen_user_id: str,
    ticket_id: str | None,
    reason_code: str,
    original_event_id: str,
    rule_version: str = RULE_VERSION,
) -> str:
    ticket_part = ticket_id or "none"
    return f"rev:{citizen_user_id}:{ticket_part}:{reason_code}:{original_event_id}:{rule_version}"


def ops_event_key(*, citizen_user_id: str, adjustment_id: str) -> str:
    return f"ops:{citizen_user_id}:{adjustment_id}"


def monthly_period_key(iso_timestamp: str) -> str:
    return iso_timestamp[:7]


def invert_sort_points(points: int) -> str:
    bounded = max(0, min(points, 9_999_999_999))
    return f"{9_999_999_999 - bounded:010d}"


def ranking_sort_key(*, points: int, first_award_at: str, citizen_user_id: str) -> str:
    return f"{invert_sort_points(points)}#{first_award_at}#{citizen_user_id}"


def level_for_points(points: int) -> tuple[str, str]:
    current = LEVELS[0]
    for level_id, minimum, title in LEVELS:
        if points >= minimum:
            current = (level_id, title)
    return current


def next_level(points: int) -> tuple[str, str, int] | None:
    for level_id, minimum, title in LEVELS:
        if points < minimum:
            return level_id, title, minimum - points
    return None


def earned_badges(points: int) -> list[str]:
    return [title for _level_id, minimum, title in LEVELS if points >= minimum and minimum > 0]


def sanitize_public_display_name(full_name: str | None) -> str | None:
    if not full_name:
        return None
    collapsed = " ".join(full_name.split())
    if not collapsed or len(collapsed) > 80:
        return None
    if "@" in collapsed or _PHONE_LIKE.search(collapsed):
        return None
    return collapsed


def citizen_reason(reason_code: str) -> Literal[
    "accepted",
    "in_progress",
    "resolved",
    "supporting",
    "reviewing",
    "adjusted",
    "adjustment",
]:
    return CITIZEN_REASON_MAP.get(reason_code, "adjusted")
