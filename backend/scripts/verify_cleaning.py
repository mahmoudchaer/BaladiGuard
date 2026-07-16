"""Optional live Bedrock smoke test for issue #18 description cleaning.

Requires AWS credentials with Bedrock Runtime access and model enabled:
  BEDROCK_MODEL_ID=amazon.nova-lite-v1:0  (default)
  AWS_REGION=us-east-1
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY

Usage (from backend/):
  python scripts/verify_cleaning.py
  python scripts/verify_cleaning.py --limit 8
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.cleaning import MAX_CLEANED_DESCRIPTION_LENGTH  # noqa: E402
from app.services.ai.bedrock_client import (  # noqa: E402
    BedrockClassificationClient,
    BedrockCleaningError,
)
from app.services.ai.clean import SYSTEM_PROMPT, clean_report_description  # noqa: E402

MULTILINGUAL_PATH = BACKEND_ROOT / "tests" / "fixtures" / "ai_intake_multilingual_cases.json"


def _probe_bedrock_access() -> None:
    client = BedrockClassificationClient()
    try:
        client.clean_description(
            system_prompt=SYSTEM_PROMPT,
            user_text="Probe request: large pothole on a public street.",
        )
    except BedrockCleaningError as exc:
        cause = exc.__cause__ or exc
        raise SystemExit(
            "BEDROCK_ACCESS_ERROR: "
            f"{cause}\n\n"
            "Enable model access in the Bedrock console and attach IAM permission "
            "bedrock:InvokeModel (and bedrock:InvokeModelWithResponseStream if needed) "
            f"for model {client.model_id} in {client.region_name}."
        ) from exc


def _run_cases(limit: int) -> list[dict]:
    dataset = json.loads(MULTILINGUAL_PATH.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for case in dataset["cases"][:limit]:
        result = clean_report_description(case["input"])
        rows.append(
            {
                "id": case["id"],
                "languageTags": case["languageTags"],
                "input": case["input"],
                "cleaned": result.cleaned_description,
                "usedFallback": result.used_fallback,
                "message": result.message,
                "mustPreserve": case["cleaningExpectations"]["mustPreserve"],
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Live Bedrock description cleaning check")
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of multilingual cases to run (default: 5)",
    )
    args = parser.parse_args()

    print("=== Probing Bedrock access ===")
    _probe_bedrock_access()
    print("Bedrock access OK\n")

    print("=== Description cleaning (live Bedrock) ===")
    rows = _run_cases(args.limit)
    successes = 0
    for row in rows:
        ok = row["cleaned"] is not None and not row["usedFallback"]
        flag = "OK" if ok else "FALLBACK"
        if ok:
            successes += 1
        print(f"[{flag}] {row['id']} ({', '.join(row['languageTags'])})")
        print(f"       input:   {row['input'][:120]}{'...' if len(row['input']) > 120 else ''}")
        if row["cleaned"]:
            cleaned = row["cleaned"]
            print(
                f"       cleaned: {cleaned[:120]}{'...' if len(cleaned) > 120 else ''} "
                f"({len(cleaned)} chars, max {MAX_CLEANED_DESCRIPTION_LENGTH})"
            )
        else:
            print(f"       message: {row['message']}")
        print(f"       preserve: {', '.join(row['mustPreserve'][:4])}")

    print(f"\nCLEANING_VERIFY {successes}/{len(rows)} produced cleaned descriptions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
