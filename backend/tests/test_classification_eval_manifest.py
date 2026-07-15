"""CI-safe validation for the live classification eval manifest (no Bedrock calls)."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.ai.categories import allowed_category_ids

MANIFEST_PATH = Path(__file__).parent / "fixtures" / "classification_eval_manifest.json"
CATEGORY_PATH = Path(__file__).parents[1] / "scripts" / "db" / "seeds" / "categories.json"


def test_classification_eval_manifest_is_valid() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    categories = json.loads(CATEGORY_PATH.read_text(encoding="utf-8"))
    category_ids = {item["categoryId"] for item in categories}
    assert category_ids == allowed_category_ids()

    assert manifest["schemaVersion"] == "1.0"
    assert manifest["uncategorizedCategory"] == "PENDING_CLASSIFICATION"
    cases = manifest["cases"]
    assert 10 <= len(cases) <= 30

    modalities = {case.get("modality", "text") for case in cases}
    assert "text" in modalities
    assert "image" in modalities
    assert (
        "multimodal" in modalities
        or len([case for case in cases if case.get("modality") == "image"]) >= 2
    )

    text_cases = [case for case in cases if case.get("modality", "text") == "text"]
    visual_cases = [case for case in cases if case.get("modality") in {"image", "multimodal"}]
    assert len(text_cases) >= 8
    assert len(visual_cases) >= 3
    assert any(case.get("modality") == "image" for case in visual_cases)

    pending_cases = [
        case for case in text_cases if case["expectedCategory"] == "PENDING_CLASSIFICATION"
    ]
    assert len(pending_cases) >= 2

    seen_ids: set[str] = set()
    for case in cases:
        assert case["id"]
        assert case["id"] not in seen_ids
        seen_ids.add(case["id"])
        assert case["expectedCategory"] in category_ids
        assert case.get("notes")

        modality = case.get("modality", "text")
        if modality == "text":
            assert case.get("description")
            assert not case.get("imageRef")
            assert not case.get("imageUrl")
            assert not case.get("imageObjectKey")
        elif modality in {"image", "multimodal"}:
            has_ref = bool(
                case.get("imageRef") or case.get("imageUrl") or case.get("imageObjectKey")
            )
            assert has_ref, case["id"]
            if modality == "multimodal":
                assert case.get("description"), case["id"]
            # Keep image binaries out of the repo: refs must be external pointers.
            for key in ("imageRef", "imageUrl", "imageObjectKey"):
                value = case.get(key)
                if value:
                    assert not str(value).startswith("backend/")
                    assert "\\" not in str(value)
        else:
            raise AssertionError(f"unknown modality: {modality}")

    image_source = manifest["imageSource"]
    assert image_source["s3PrefixEnv"] == "CLASSIFICATION_EVAL_S3_PREFIX"
    assert image_source["urlBaseEnv"] == "CLASSIFICATION_EVAL_IMAGE_BASE_URL"
