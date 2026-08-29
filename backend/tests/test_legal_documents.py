"""Public legal document catalog and markdown loading (issue #321)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.services.legal.documents import (
    CURRENT_LEGAL_VERSION,
    DOCUMENT_IDS,
    SUPPORTED_LANGS,
    clear_document_cache,
    find_legal_docs_root,
    load_document,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DOCKERFILE = BACKEND_ROOT / "Dockerfile"
PACKAGED_LEGAL = BACKEND_ROOT / "legal"


def test_legal_catalog_lists_current_package(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/v1/legal")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == CURRENT_LEGAL_VERSION
    ids = [doc["id"] for doc in body["documents"]]
    assert ids == list(DOCUMENT_IDS)
    for doc in body["documents"]:
        assert doc["version"] == CURRENT_LEGAL_VERSION
        assert doc["languages"] == ["en", "ar", "fr"]
        assert doc["title"]
        assert doc["updatedAt"].startswith(CURRENT_LEGAL_VERSION)


def test_legal_document_fetch_en_ar_fr_and_fallback(anonymous_client: TestClient) -> None:
    clear_document_cache()
    for lang in ("en", "ar", "fr"):
        response = anonymous_client.get(f"/v1/legal/privacy?lang={lang}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["id"] == "privacy"
        assert body["lang"] == lang
        assert body["version"] == CURRENT_LEGAL_VERSION
        assert (
            "Product draft" in body["markdown"]
            or "مسودة منتج" in body["markdown"]
            or ("Brouillon produit" in body["markdown"])
        )
        assert "privacy@baladiguard.app" in body["markdown"]

    fallback = anonymous_client.get("/v1/legal/terms?lang=xx")
    assert fallback.status_code == 200
    assert fallback.json()["lang"] == "en"


def test_unknown_legal_document_is_404(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/v1/legal/not-a-doc")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_load_document_reads_repo_markdown() -> None:
    clear_document_cache()
    loaded = load_document("acceptable-use", "en")
    assert loaded is not None
    assert loaded["id"] == "acceptable-use"
    assert "16" in loaded["markdown"]


def test_backend_image_packages_legal_documents() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY legal ./legal" in dockerfile
    for lang in SUPPORTED_LANGS:
        for document_id in DOCUMENT_IDS:
            packaged = PACKAGED_LEGAL / lang / f"{document_id}.md"
            checkout = REPO_ROOT / "docs" / "legal" / lang / f"{document_id}.md"
            assert packaged.is_file(), packaged
            assert checkout.is_file(), checkout
            assert packaged.read_text(encoding="utf-8") == checkout.read_text(encoding="utf-8")


def test_find_legal_docs_root_uses_image_layout_without_repo_docs(tmp_path: Path) -> None:
    fake_module = tmp_path / "app" / "services" / "legal" / "documents.py"
    fake_module.parent.mkdir(parents=True)
    fake_module.write_text("# stub\n", encoding="utf-8")
    packaged = tmp_path / "legal"
    for lang in SUPPORTED_LANGS:
        (packaged / lang).mkdir(parents=True)
        for document_id in DOCUMENT_IDS:
            (packaged / lang / f"{document_id}.md").write_text(
                f"# {document_id}\n",
                encoding="utf-8",
            )
    isolated_cwd = tmp_path / "isolated-cwd"
    isolated_cwd.mkdir()

    root = find_legal_docs_root(start_file=fake_module, cwd=isolated_cwd)
    assert root == packaged
    assert not (isolated_cwd / "docs" / "legal").exists()
