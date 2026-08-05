"""Load starter reference data into DynamoDB."""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.seeding import run_seed


def main() -> None:
    parser = ArgumentParser(description="Load BaladiGuard reference and optional demo data.")
    parser.add_argument(
        "--with-samples",
        action="store_true",
        help="Load the Sprint 6 synthetic sample ticket story regardless of SEED_SAMPLE_TICKETS.",
    )
    args = parser.parse_args()

    run_seed(with_samples=True if args.with_samples else None)
    print("Seed complete.")


if __name__ == "__main__":
    main()
