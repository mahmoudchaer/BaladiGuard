"""Legal document catalog and markdown loader (issue #321)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

CURRENT_LEGAL_VERSION = "2026-08-22"
DOCUMENT_IDS: tuple[str, ...] = ("terms", "privacy", "acceptable-use")
SUPPORTED_LANGS: tuple[str, ...] = ("en", "ar", "fr")
DEFAULT_LANG = "en"
LegalDocumentId = Literal["terms", "privacy", "acceptable-use"]
LegalLang = Literal["en", "ar", "fr"]

_DOCUMENT_TITLES: dict[str, dict[str, str]] = {
    "terms": {
        "en": "Terms of Service",
        "ar": "شروط الخدمة",
        "fr": "Conditions d’utilisation",
    },
    "privacy": {
        "en": "Privacy Policy",
        "ar": "سياسة الخصوصية",
        "fr": "Politique de confidentialité",
    },
    "acceptable-use": {
        "en": "Acceptable Use Policy",
        "ar": "سياسة الاستخدام المقبول",
        "fr": "Politique d’usage acceptable",
    },
}


def _is_legal_package(path: Path) -> bool:
    """True when ``path`` has the packaged ``{lang}/{document}.md`` layout."""
    english = path / DEFAULT_LANG
    if not english.is_dir():
        return False
    return any((english / f"{document_id}.md").is_file() for document_id in DOCUMENT_IDS)


def find_legal_docs_root(
    *,
    start_file: Path | None = None,
    cwd: Path | None = None,
) -> Path:
    """Locate packaged legal markdown for checkout and the backend image.

    Production image layout (``backend`` Docker context): ``/app/legal``.
    Checkout also keeps a browsable copy at repository-root ``docs/legal``.
    Packaged ``legal/`` is preferred so public ``/v1/legal`` works without the
    repo-root docs tree.
    """
    here = (start_file or Path(__file__)).resolve()
    working = (cwd or Path.cwd()).resolve()
    search_roots: list[Path] = [here.parent, *here.parents, working, *working.parents]
    seen: set[Path] = set()
    for parent in search_roots:
        if parent in seen:
            continue
        seen.add(parent)
        packaged = parent / "legal"
        if _is_legal_package(packaged):
            return packaged
        checkout = parent / "docs" / "legal"
        if _is_legal_package(checkout):
            return checkout
    raise FileNotFoundError(
        "Packaged legal documents not found. Expected backend/legal "
        "(copied into /app/legal in the backend image) or docs/legal."
    )


def normalize_lang(lang: str | None) -> str:
    if lang is None:
        return DEFAULT_LANG
    trimmed = lang.strip().lower()
    if trimmed in SUPPORTED_LANGS:
        return trimmed
    return DEFAULT_LANG


def document_title(document_id: str, lang: str = DEFAULT_LANG) -> str:
    titles = _DOCUMENT_TITLES.get(document_id) or {}
    return titles.get(lang) or titles.get(DEFAULT_LANG) or document_id


def catalog_documents() -> list[dict[str, object]]:
    updated_at = f"{CURRENT_LEGAL_VERSION}T00:00:00Z"
    return [
        {
            "id": document_id,
            "title": document_title(document_id, DEFAULT_LANG),
            "version": CURRENT_LEGAL_VERSION,
            "updatedAt": updated_at,
            "languages": list(SUPPORTED_LANGS),
        }
        for document_id in DOCUMENT_IDS
    ]


@lru_cache(maxsize=32)
def _read_markdown(document_id: str, lang: str) -> str | None:
    if document_id not in DOCUMENT_IDS:
        return None
    root = find_legal_docs_root()
    path = root / lang / f"{document_id}.md"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def load_document(document_id: str, lang: str | None = None) -> dict[str, object] | None:
    """Load markdown for ``document_id``; fall back to English when needed."""
    if document_id not in DOCUMENT_IDS:
        return None
    requested = normalize_lang(lang)
    body = _read_markdown(document_id, requested)
    resolved_lang = requested
    if body is None and requested != DEFAULT_LANG:
        body = _read_markdown(document_id, DEFAULT_LANG)
        resolved_lang = DEFAULT_LANG
    if body is None:
        return None
    return {
        "id": document_id,
        "title": document_title(document_id, resolved_lang),
        "version": CURRENT_LEGAL_VERSION,
        "updatedAt": f"{CURRENT_LEGAL_VERSION}T00:00:00Z",
        "lang": resolved_lang,
        "markdown": body,
    }


def clear_document_cache() -> None:
    _read_markdown.cache_clear()
