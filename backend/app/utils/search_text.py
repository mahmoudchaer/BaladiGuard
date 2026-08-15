"""Shared case-insensitive search matching for staff global search."""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")
_COMPACT_RE = re.compile(r"[\s\-]+")


def normalize_search_query(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value.strip())


def compact_search_text(value: str) -> str:
    return _COMPACT_RE.sub("", value).casefold()


def search_text_contains(haystack: str | None, needle: str) -> bool:
    if not haystack:
        return False
    compact_needle = compact_search_text(needle)
    return needle.casefold() in haystack.casefold() or (
        bool(compact_needle) and compact_needle in compact_search_text(haystack)
    )
