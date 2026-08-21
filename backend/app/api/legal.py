"""Public legal document endpoints (issue #321)."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.core.errors import build_error_response, get_request_id
from app.schemas.legal import LegalCatalogResponse, LegalDocumentResponse, LegalDocumentSummary
from app.services.legal.documents import (
    CURRENT_LEGAL_VERSION,
    DOCUMENT_IDS,
    catalog_documents,
    load_document,
)

router = APIRouter(prefix="/v1/legal", tags=["legal"])


@router.get("", response_model=LegalCatalogResponse)
def get_legal_catalog() -> LegalCatalogResponse:
    return LegalCatalogResponse(
        version=CURRENT_LEGAL_VERSION,
        documents=[LegalDocumentSummary.model_validate(item) for item in catalog_documents()],
    )


@router.get("/{document_id}", response_model=LegalDocumentResponse)
def get_legal_document(
    document_id: str,
    request: Request,
    lang: str | None = Query(default="en"),
) -> LegalDocumentResponse | JSONResponse:
    if document_id not in DOCUMENT_IDS:
        return build_error_response(
            code="NOT_FOUND",
            message="Legal document not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    loaded = load_document(document_id, lang)
    if loaded is None:
        return build_error_response(
            code="NOT_FOUND",
            message="Legal document not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    return LegalDocumentResponse.model_validate(loaded)
