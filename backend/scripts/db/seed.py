"""Load starter reference data into DynamoDB."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.seeding import run_seed


def main() -> None:
    run_seed()
    print("Seed complete.")


if __name__ == "__main__":
    main()
