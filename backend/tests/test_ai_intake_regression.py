"""Deterministic, provider-free AI intake regressions for issue #70."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.schemas.stored_ticket import PENDING_CLASSIFICATION
from app.services.ai.categories import allowed_category_ids
from app.services.ai.classify import classify_complaint
from app.services.ai.clean import clean_report_description

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DATASET_PATH = FIXTURES_DIR / "ai_intake_multilingual_cases.json"
OUTPUTS_PATH = FIXTURES_DIR / "ai_intake_deterministic_outputs.json"


def _load_fixtures() -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    deterministic = json.loads(OUTPUTS_PATH.read_text(encoding="utf-8"))
    assert deterministic["datasetId"] == dataset["datasetId"]
    return dataset["cases"], deterministic["outputs"]


CASES, DETERMINISTIC_OUTPUTS = _load_fixtures()

pytestmark = pytest.mark.ai_intake_regression


class DeterministicBedrockClient:
    """Small provider double returning one reviewed golden result."""

    def __init__(self, output: dict[str, str]) -> None:
        self.output = output
        self.classification_calls: list[dict[str, Any]] = []
        self.cleaning_calls: list[dict[str, Any]] = []

    def classify(self, **kwargs: Any) -> dict[str, str]:
        self.classification_calls.append(kwargs)
        return {
            "category": self.output["category"],
            "explanation": "Deterministic regression response.",
        }

    def clean_description(self, **kwargs: Any) -> dict[str, str]:
        self.cleaning_calls.append(kwargs)
        return {"cleanedDescription": self.output["cleanedDescription"]}


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _missing_details(cleaned: str, expected: list[str]) -> list[str]:
    normalized = _normalized(cleaned)
    return [detail for detail in expected if _normalized(detail) not in normalized]


def _invented_details(cleaned: str, prohibited: list[str]) -> list[str]:
    normalized = _normalized(cleaned)
    return [detail for detail in prohibited if _normalized(detail) in normalized]


def test_deterministic_outputs_match_every_dataset_case() -> None:
    case_ids = {case["id"] for case in CASES}
    output_ids = set(DETERMINISTIC_OUTPUTS)

    assert output_ids == case_ids, (
        "Deterministic output IDs must exactly match the multilingual dataset. "
        f"missing={sorted(case_ids - output_ids)!r}, extra={sorted(output_ids - case_ids)!r}"
    )


def test_regression_set_covers_categories_languages_and_safe_fallback() -> None:
    categories = {case["expectedCategory"] for case in CASES}
    languages = {tag for case in CASES for tag in case["languageTags"]}
    ambiguous_ids = {case["id"] for case in CASES if "ambiguous" in case["id"]}

    assert categories == allowed_category_ids()
    assert {"ar", "fr", "arabizi", "mixed"} <= languages
    assert PENDING_CLASSIFICATION in categories
    assert ambiguous_ids == {
        "ai-multi-011-road-vs-drainage-ambiguous",
        "ai-multi-012-waste-vs-noise-ambiguous-arabizi",
    }


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_classification_regression(case: dict[str, Any]) -> None:
    output = DETERMINISTIC_OUTPUTS[case["id"]]
    client = DeterministicBedrockClient(output)

    result = classify_complaint(
        case["input"],
        client=client,  # type: ignore[arg-type]
    )

    assert result.category == case["expectedCategory"], (
        f"case={case['id']}\n"
        f"input={case['input']!r}\n"
        f"expected_category={case['expectedCategory']!r}\n"
        f"actual_category={result.category!r}\n"
        f"explanation={result.explanation!r}"
    )
    assert len(client.classification_calls) == 1
    assert case["input"] in client.classification_calls[0]["user_text"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_cleaning_regression_preserves_details_without_fabrication(
    case: dict[str, Any],
) -> None:
    output = DETERMINISTIC_OUTPUTS[case["id"]]
    client = DeterministicBedrockClient(output)

    result = clean_report_description(
        case["input"],
        client=client,  # type: ignore[arg-type]
    )

    expectations = case["cleaningExpectations"]
    actual = result.cleaned_description or ""
    missing = _missing_details(actual, expectations["mustPreserve"])
    invented = _invented_details(actual, expectations["mustNotInvent"])

    assert result.cleaned_description is not None and not result.used_fallback, (
        f"case={case['id']}\n"
        f"input={case['input']!r}\n"
        f"expected=successful cleaned description\n"
        f"actual={result.model_dump(by_alias=True)!r}"
    )
    assert not missing, (
        f"case={case['id']}\n"
        f"input={case['input']!r}\n"
        f"expected_preserved={expectations['mustPreserve']!r}\n"
        f"missing={missing!r}\n"
        f"actual_cleaned={actual!r}\n"
        f"semantic_expectations={expectations['requiredProperties']!r}"
    )
    assert not invented, (
        f"case={case['id']}\n"
        f"input={case['input']!r}\n"
        f"prohibited_details={expectations['mustNotInvent']!r}\n"
        f"invented={invented!r}\n"
        f"actual_cleaned={actual!r}"
    )
    assert len(client.cleaning_calls) == 1
    assert case["input"] in client.cleaning_calls[0]["user_text"]


def test_no_fabrication_checker_detects_prohibited_details() -> None:
    case = CASES[0]
    prohibited = case["cleaningExpectations"]["mustNotInvent"]
    deliberately_bad = (
        DETERMINISTIC_OUTPUTS[case["id"]]["cleanedDescription"] + " Injuries were reported."
    )

    assert _invented_details(deliberately_bad, prohibited) == ["injuries"]
