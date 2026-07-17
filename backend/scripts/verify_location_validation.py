"""Optional live Amazon Location smoke test for issue #24.

Requires:
  LOCATION_PLACE_INDEX_NAME=<your place index>
  AWS_REGION=us-east-1
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY

Usage (from backend/):
  python scripts/verify_location_validation.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.location_validation import ValidateLocationRequest  # noqa: E402
from app.services.location.amazon_location_client import (  # noqa: E402
    AmazonLocationClient,
    LocationProviderError,
)
from app.services.location.validate_location import validate_location  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Live Amazon Location validation check")
    parser.add_argument(
        "--address",
        default="AUB Main Gate, Hamra, Beirut",
        help="Address text to geocode",
    )
    args = parser.parse_args()

    index_name = os.environ.get("LOCATION_PLACE_INDEX_NAME", "").strip()
    if not index_name:
        raise SystemExit(
            "LOCATION_PLACE_INDEX_NAME is required for the live verification script.\n"
            "Create an Amazon Location place index and set the env var first."
        )

    client = AmazonLocationClient(index_name=index_name)
    print("=== Probing Amazon Location access ===")
    try:
        client.geocode_address(args.address)
    except LocationProviderError as exc:
        cause = exc.__cause__ or exc
        raise SystemExit(f"LOCATION_ACCESS_ERROR: {cause}") from exc
    print("Amazon Location access OK\n")

    print("=== Address validation ===")
    address_result = validate_location(
        ValidateLocationRequest(addressText=args.address),
        provider=client,
    )
    print(address_result.model_dump(by_alias=True))

    if address_result.location is not None:
        print("\n=== Coordinate reverse validation ===")
        reverse_result = validate_location(
            ValidateLocationRequest(
                latitude=address_result.location.latitude,
                longitude=address_result.location.longitude,
            ),
            provider=client,
        )
        print(reverse_result.model_dump(by_alias=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
