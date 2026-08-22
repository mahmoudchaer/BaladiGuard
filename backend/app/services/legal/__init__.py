"""Legal package helpers (issue #321)."""

from app.services.legal.documents import (
    CURRENT_LEGAL_VERSION,
    DOCUMENT_IDS,
    catalog_documents,
    clear_document_cache,
    load_document,
)

__all__ = [
    "CURRENT_LEGAL_VERSION",
    "DOCUMENT_IDS",
    "catalog_documents",
    "clear_document_cache",
    "load_document",
]
