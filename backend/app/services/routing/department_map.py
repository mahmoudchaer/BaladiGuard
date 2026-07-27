"""Canonical category → department mapping for MVP routing."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

SEEDS_DIR = Path(__file__).resolve().parents[3] / "scripts" / "db" / "seeds"
CATEGORY_SEED_PATH = SEEDS_DIR / "categories.json"
DEPARTMENT_SEED_PATH = SEEDS_DIR / "departments.json"


@lru_cache
def load_department_catalog() -> tuple[dict[str, str], ...]:
    raw = json.loads(DEPARTMENT_SEED_PATH.read_text(encoding="utf-8"))
    return tuple(
        {
            "departmentId": item["departmentId"],
            "municipalityId": item["municipalityId"],
            "name": item["name"],
            "description": item["description"],
        }
        for item in raw
    )


@lru_cache
def load_category_department_rows() -> tuple[dict[str, str | None], ...]:
    raw = json.loads(CATEGORY_SEED_PATH.read_text(encoding="utf-8"))
    rows: list[dict[str, str | None]] = []
    for item in raw:
        department_id = item.get("departmentId")
        rows.append(
            {
                "categoryId": item["categoryId"],
                "departmentId": department_id if isinstance(department_id, str) else None,
            }
        )
    return tuple(rows)


@lru_cache
def category_to_department_map() -> dict[str, str]:
    """Return concrete categoryId → departmentId mappings (excludes unmapped categories)."""
    return {
        row["categoryId"]: row["departmentId"]
        for row in load_category_department_rows()
        if row["departmentId"] is not None
    }


def department_id_for_category(category_id: str) -> str | None:
    """Resolve the responsible department for a category, or None if unmapped."""
    return category_to_department_map().get(category_id)


def suggest_department_id(
    *,
    category_id: str | None,
    urgency_level: str | None = None,
    urgency_score: int | None = None,
) -> str | None:
    """Suggest the responsible department from seeded routing rules.

    Urgency is accepted as part of the processed-ticket context so rule sets can
    evolve later. The current MVP rule source maps category to department and
    does not reroute tickets by urgency.
    """
    if category_id is None:
        return None
    return department_id_for_category(category_id)


def department_ids() -> frozenset[str]:
    return frozenset(item["departmentId"] for item in load_department_catalog())


def department_name(department_id: str) -> str | None:
    for item in load_department_catalog():
        if item["departmentId"] == department_id:
            return item["name"]
    return None
