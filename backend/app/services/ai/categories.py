"""MVP complaint category allowlist for AI classification."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.schemas.stored_ticket import PENDING_CLASSIFICATION

CATEGORY_SEED_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "db" / "seeds" / "categories.json"
)


@lru_cache
def load_category_catalog() -> tuple[dict[str, str], ...]:
    raw = json.loads(CATEGORY_SEED_PATH.read_text(encoding="utf-8"))
    return tuple(
        {
            "categoryId": item["categoryId"],
            "label": item["label"],
            "description": item["description"],
        }
        for item in raw
    )


def allowed_category_ids() -> frozenset[str]:
    return frozenset(item["categoryId"] for item in load_category_catalog())


def concrete_category_ids() -> frozenset[str]:
    return allowed_category_ids() - {PENDING_CLASSIFICATION}


def format_category_list_for_prompt() -> str:
    lines = []
    for item in load_category_catalog():
        lines.append(f"- `{item['categoryId']}` ({item['label']}): {item['description']}")
    return "\n".join(lines)
