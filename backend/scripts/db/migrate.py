"""Create DynamoDB tables for the MVP persistence model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.migrations import run_migrations


def main() -> None:
    parser = argparse.ArgumentParser(description="Create BaladiGuard DynamoDB tables.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing project tables before creating them.",
    )
    args = parser.parse_args()
    run_migrations(reset=args.reset)
    print("Migration complete.")
    print(
        "If status/audit/comment rows already exist, finish "
        "`python scripts/db/backfill_activity_timeline_keys.py` "
        "(or `make db-backfill-activity-timeline`) before setting "
        "ACTIVITY_TIMELINE_USE_GSI=true."
    )


if __name__ == "__main__":
    main()
