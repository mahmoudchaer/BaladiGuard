"""Optional live Bedrock smoke test for issue #17 classification.

Requires AWS credentials with Bedrock Runtime access and model enabled:
  BEDROCK_MODEL_ID=amazon.nova-lite-v1:0  (default)
  AWS_REGION=us-east-1
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY

Usage (from backend/):
  python scripts/verify_classification.py

For the full labeled accuracy suite (text + external images), use:
  python scripts/eval_classification.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ai.bedrock_client import (  # noqa: E402
    BedrockClassificationClient,
    BedrockClassificationError,
)
from app.services.ai.categories import format_category_list_for_prompt  # noqa: E402
from app.services.ai.classify import classify_complaint  # noqa: E402

MULTILINGUAL_PATH = BACKEND_ROOT / "tests" / "fixtures" / "ai_intake_multilingual_cases.json"


def _probe_bedrock_access() -> None:
    client = BedrockClassificationClient()
    try:
        client.classify(
            system_prompt=(
                "You are a classifier. Categories:\n" + format_category_list_for_prompt()
            ),
            user_text="Probe request: large pothole on a public street.",
        )
    except BedrockClassificationError as exc:
        cause = exc.__cause__ or exc
        raise SystemExit(
            "BEDROCK_ACCESS_ERROR: "
            f"{cause}\n\n"
            "Enable model access in the Bedrock console and attach IAM permission "
            "bedrock:InvokeModel (and bedrock:InvokeModelWithResponseStream if needed) "
            f"for model {client.model_id} in {client.region_name}."
        ) from exc


def _run_text_cases(limit: int) -> list[dict]:
    dataset = json.loads(MULTILINGUAL_PATH.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for case in dataset["cases"][:limit]:
        result = classify_complaint(case["input"])
        rows.append(
            {
                "id": case["id"],
                "expected": case["expectedCategory"],
                "got": result.category,
                "match": result.category == case["expectedCategory"],
                "explanation": result.explanation,
                "usedInputs": result.used_inputs.model_dump(by_alias=True),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Live Bedrock classification check")
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of multilingual text cases to run (default: 5)",
    )
    args = parser.parse_args()

    print("=== Probing Bedrock access ===")
    _probe_bedrock_access()
    print("Bedrock access OK\n")

    print("=== Text classification (live Bedrock) ===")
    text_rows = _run_text_cases(args.limit)
    for row in text_rows:
        flag = "OK" if row["match"] else "MISS"
        print(f"[{flag}] {row['id']}: expected={row['expected']} got={row['got']}")
        print(f"       {row['explanation']}")

    matches = sum(1 for row in text_rows if row["match"])
    print(f"\nCLASSIFICATION_VERIFY {matches}/{len(text_rows)} matched")
    # Soft success: script ran against Bedrock; mismatches are reported for review.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
