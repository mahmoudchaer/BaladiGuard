import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


def load_environment() -> None:
    load_dotenv(BACKEND_DIR / ".env", override=True)
    load_dotenv(REPO_ROOT / ".env", override=True)


load_environment()


class Settings:
    def __init__(self) -> None:
        self.database_backend = os.getenv("DATABASE_BACKEND", "memory").strip().lower()
        self.aws_region = os.getenv("AWS_REGION", "us-east-1").strip()
        endpoint = os.getenv("DYNAMODB_ENDPOINT_URL", "").strip()
        self.dynamodb_endpoint_url = endpoint or None
        self.dynamodb_table_prefix = os.getenv("DYNAMODB_TABLE_PREFIX", "baladiguard-").strip()
        self.seed_sample_tickets = (
            os.getenv("SEED_SAMPLE_TICKETS", "false").strip().lower() == "true"
        )

    @property
    def use_dynamodb(self) -> bool:
        return self.database_backend == "dynamodb"


@lru_cache
def get_settings() -> Settings:
    return Settings()
