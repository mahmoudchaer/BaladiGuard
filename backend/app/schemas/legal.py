"""Public legal document API schemas (issue #321)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LegalDocumentSummary(BaseModel):
    id: str
    title: str
    version: str
    updated_at: str = Field(alias="updatedAt")
    languages: list[str]

    model_config = {"populate_by_name": True}


class LegalCatalogResponse(BaseModel):
    version: str
    documents: list[LegalDocumentSummary]

    model_config = {"populate_by_name": True}


class LegalDocumentResponse(BaseModel):
    id: str
    title: str
    version: str
    updated_at: str = Field(alias="updatedAt")
    lang: str
    markdown: str

    model_config = {"populate_by_name": True}
