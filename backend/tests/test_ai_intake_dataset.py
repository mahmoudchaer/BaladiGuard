import json
from pathlib import Path

DATASET_PATH = Path(__file__).parent / "fixtures" / "ai_intake_multilingual_cases.json"
CATEGORY_PATH = Path(__file__).parents[1] / "scripts" / "db" / "seeds" / "categories.json"


def test_ai_intake_dataset_is_valid_and_covers_mvp_categories() -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    categories = json.loads(CATEGORY_PATH.read_text(encoding="utf-8"))

    category_ids = {category["categoryId"] for category in categories}
    cases = dataset["cases"]
    case_categories = {case["expectedCategory"] for case in cases}
    language_tags = {tag for case in cases for tag in case["languageTags"]}

    assert dataset["schemaVersion"] == "1.0"
    assert dataset["uncategorizedCategory"] == "PENDING_CLASSIFICATION"
    assert category_ids <= case_categories
    assert {"en", "ar", "fr", "arabizi", "mixed"} <= language_tags

    for case in cases:
        assert case["id"]
        assert case["input"]
        assert case["expectedCategory"] in category_ids
        assert case["classificationNotes"]

        expectations = case["cleaningExpectations"]
        assert expectations["requiredProperties"], case["id"]
        assert expectations["mustPreserve"], case["id"]
        assert expectations["mustNotInvent"], case["id"]
