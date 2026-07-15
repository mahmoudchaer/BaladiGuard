"""Manual labeled Bedrock classification evaluation (not run in CI).

Uses backend/tests/fixtures/classification_eval_manifest.json:
  - text cases are in-repo
  - image binaries stay outside the repo (S3 keys or HTTPS URLs)

Environment (optional unless image cases are run):
  CLASSIFICATION_EVAL_S3_PREFIX=classification-eval/
  CLASSIFICATION_EVAL_S3_BUCKET=   # defaults to AWS_S3_BUCKET
  CLASSIFICATION_EVAL_IMAGE_BASE_URL=  # optional HTTPS base for imageRef
  AWS credentials + BEDROCK_MODEL_ID as usual

Usage (from backend/):
  python scripts/eval_classification.py
  python scripts/eval_classification.py --text-only
  python scripts/eval_classification.py --images-only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ai.bedrock_client import (  # noqa: E402
    BedrockClassificationClient,
    BedrockClassificationError,
)
from app.services.ai.categories import format_category_list_for_prompt  # noqa: E402
from app.services.ai.classify import classify_complaint  # noqa: E402

DEFAULT_MANIFEST_PATH = BACKEND_ROOT / "tests" / "fixtures" / "classification_eval_manifest.json"
DEFAULT_S3_PREFIX = "classification-eval/"


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
            "bedrock:InvokeModel for "
            f"model {client.model_id} in {client.region_name}."
        ) from exc


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _s3_client():
    import boto3

    region = os.environ.get("AWS_REGION", "us-east-1").strip() or "us-east-1"
    kwargs: dict = {"region_name": region}
    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
    if access_key and secret_key:
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret_key
    return boto3.client("s3", **kwargs)


def _eval_bucket() -> str:
    bucket = (
        os.environ.get("CLASSIFICATION_EVAL_S3_BUCKET", "").strip()
        or os.environ.get("AWS_S3_BUCKET", "").strip()
    )
    if not bucket:
        raise RuntimeError(
            "Set CLASSIFICATION_EVAL_S3_BUCKET or AWS_S3_BUCKET for image eval cases."
        )
    return bucket


def _eval_prefix() -> str:
    prefix = os.environ.get("CLASSIFICATION_EVAL_S3_PREFIX", DEFAULT_S3_PREFIX).strip()
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return prefix or DEFAULT_S3_PREFIX


def _fetch_https(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "BaladiGuardClassificationEval/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()


def _load_image_bytes(case: dict) -> bytes:
    absolute_url = (case.get("imageUrl") or "").strip()
    if absolute_url:
        return _fetch_https(absolute_url)

    image_ref = (case.get("imageRef") or "").strip()
    object_key = (case.get("imageObjectKey") or "").strip()

    if object_key:
        response = _s3_client().get_object(Bucket=_eval_bucket(), Key=object_key)
        return response["Body"].read()

    if not image_ref:
        raise RuntimeError(f"Case {case.get('id')} has no imageRef, imageObjectKey, or imageUrl.")

    if image_ref.startswith("http://") or image_ref.startswith("https://"):
        return _fetch_https(image_ref)

    base_url = os.environ.get("CLASSIFICATION_EVAL_IMAGE_BASE_URL", "").strip()
    if base_url:
        return _fetch_https(urljoin(base_url.rstrip("/") + "/", image_ref))

    key = f"{_eval_prefix()}{image_ref.lstrip('/')}"
    response = _s3_client().get_object(Bucket=_eval_bucket(), Key=key)
    return response["Body"].read()


def _run_case(case: dict) -> dict:
    case_id = case["id"]
    expected = case["expectedCategory"]
    modality = case.get("modality", "text")

    try:
        if modality == "text":
            result = classify_complaint(case.get("description"))
        elif modality in {"image", "multimodal"}:
            image_bytes = _load_image_bytes(case)
            result = classify_complaint(
                case.get("description"),
                image_bytes=image_bytes,
            )
        else:
            raise RuntimeError(f"Unknown modality: {modality}")
    except (RuntimeError, urllib.error.URLError, OSError) as exc:
        return {
            "id": case_id,
            "modality": modality,
            "expected": expected,
            "got": None,
            "match": False,
            "explanation": f"CASE_ERROR: {exc}",
            "error": True,
        }

    return {
        "id": case_id,
        "modality": modality,
        "expected": expected,
        "got": result.category,
        "match": result.category == expected,
        "explanation": result.explanation,
        "error": False,
        "usedInputs": result.used_inputs.model_dump(by_alias=True),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Manual labeled Bedrock classification evaluation")
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Run only text modality cases",
    )
    parser.add_argument(
        "--images-only",
        action="store_true",
        help="Run only image/multimodal cases",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to eval manifest JSON",
    )
    args = parser.parse_args()

    if args.text_only and args.images_only:
        raise SystemExit("Choose at most one of --text-only / --images-only")

    print("=== Probing Bedrock access ===")
    _probe_bedrock_access()
    print("Bedrock access OK\n")

    manifest = _load_manifest(args.manifest)
    cases = list(manifest["cases"])
    if args.text_only:
        cases = [case for case in cases if case.get("modality", "text") == "text"]
    elif args.images_only:
        cases = [case for case in cases if case.get("modality") in {"image", "multimodal"}]

    print(f"=== Running {len(cases)} labeled eval cases ===")
    print(f"manifest: {args.manifest}")
    print(f"model: {os.environ.get('BEDROCK_MODEL_ID', 'amazon.nova-lite-v1:0')}")
    if not args.text_only:
        print(f"s3_prefix: {_eval_prefix()}")
        try:
            print(f"s3_bucket: {_eval_bucket()}")
        except RuntimeError:
            print("s3_bucket: (unset — image cases need bucket, imageUrl, or IMAGE_BASE_URL)")
    print()

    rows = [_run_case(case) for case in cases]
    for row in rows:
        flag = "OK" if row["match"] else "MISS"
        print(
            f"[{flag}] {row['id']} ({row['modality']}): expected={row['expected']} got={row['got']}"
        )
        print(f"       {row['explanation']}")

    matched = sum(1 for row in rows if row["match"])
    errors = sum(1 for row in rows if row.get("error"))
    total = len(rows)
    accuracy = (matched / total * 100.0) if total else 0.0

    print("\n=== Summary ===")
    print(f"CLASSIFICATION_EVAL {matched}/{total} matched ({accuracy:.1f}%)")
    if errors:
        print(f"CASE_ERRORS {errors}")

    mismatches = [row for row in rows if not row["match"]]
    if mismatches:
        print("\nMismatches:")
        for row in mismatches:
            print(
                f"- {row['id']}: expected={row['expected']} got={row['got']} | {row['explanation']}"
            )

    # Manual eval: exit 0 after a successful Bedrock run so mismatches can be
    # reviewed when comparing prompts/models.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
