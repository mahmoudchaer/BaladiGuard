"""Run the full multilingual AI intake evaluation against live Bedrock.

This command is intentionally excluded from pull-request CI because it requires AWS
credentials and makes real provider calls. The deterministic CI counterpart is:

    python -m pytest -m ai_intake_regression -q

Usage from ``backend/``:

    python scripts/eval_ai_intake.py
    python scripts/eval_ai_intake.py --limit 5
    python scripts/eval_ai_intake.py --json-output artifacts/ai-intake-eval.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ai.classify import classify_complaint  # noqa: E402
from app.services.ai.clean import clean_report_description  # noqa: E402

DATASET_PATH = BACKEND_ROOT / "tests" / "fixtures" / "ai_intake_multilingual_cases.json"


def _load_cases(limit: int | None) -> list[dict[str, Any]]:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = dataset["cases"]
    return cases if limit is None else cases[:limit]


def _evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    classification = classify_complaint(case["input"])
    cleaning = clean_report_description(case["input"])
    cleaned = cleaning.cleaned_description

    return {
        "id": case["id"],
        "languageTags": case["languageTags"],
        "input": case["input"],
        "expectedCategory": case["expectedCategory"],
        "actualCategory": classification.category,
        "classificationMatch": classification.category == case["expectedCategory"],
        "classificationExplanation": classification.explanation,
        "cleanedDescription": cleaned,
        "cleaningSucceeded": cleaned is not None and not cleaning.used_fallback,
        "cleaningMessage": cleaning.message,
        "mustPreserve": case["cleaningExpectations"]["mustPreserve"],
        "mustNotInvent": case["cleaningExpectations"]["mustNotInvent"],
        "requiredProperties": case["cleaningExpectations"]["requiredProperties"],
    }


def _print_row(row: dict[str, Any]) -> None:
    classification_flag = "OK" if row["classificationMatch"] else "MISS"
    cleaning_flag = "OK" if row["cleaningSucceeded"] else "FALLBACK"
    print(
        f"[CLASSIFY {classification_flag}] {row['id']}: "
        f"expected={row['expectedCategory']} actual={row['actualCategory']}"
    )
    print(f"  input: {row['input']}")
    print(f"  explanation: {row['classificationExplanation']}")
    print(f"[CLEAN {cleaning_flag}] {row['id']}: {row['cleanedDescription']!r}")
    if row["cleaningMessage"]:
        print(f"  message: {row['cleaningMessage']}")
    print(f"  preserve: {', '.join(row['mustPreserve'])}")
    print(f"  must not invent: {', '.join(row['mustNotInvent'])}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate multilingual classification and cleaning with live Bedrock"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Evaluate only the first N cases (default: all cases)",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optionally write detailed UTF-8 JSON results for scheduled-run artifacts",
    )
    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    rows = [_evaluate_case(case) for case in _load_cases(args.limit)]
    for row in rows:
        _print_row(row)

    classification_matches = sum(row["classificationMatch"] for row in rows)
    cleaning_successes = sum(row["cleaningSucceeded"] for row in rows)
    print(
        "\nAI_INTAKE_EVAL "
        f"classification={classification_matches}/{len(rows)} "
        f"cleaning={cleaning_successes}/{len(rows)}"
    )

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps({"cases": rows}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote detailed results to {args.json_output}")

    return 0 if classification_matches == len(rows) and cleaning_successes == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
