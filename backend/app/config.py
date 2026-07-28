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
        self.aws_s3_bucket = os.getenv("AWS_S3_BUCKET", "").strip() or None
        endpoint = os.getenv("DYNAMODB_ENDPOINT_URL", "").strip()
        self.dynamodb_endpoint_url = endpoint or None
        self.dynamodb_table_prefix = os.getenv("DYNAMODB_TABLE_PREFIX", "baladiguard-").strip()
        self.seed_sample_tickets = (
            os.getenv("SEED_SAMPLE_TICKETS", "false").strip().lower() == "true"
        )
        self.bedrock_model_id = (
            os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0").strip()
            or "amazon.nova-lite-v1:0"
        )
        self.location_place_index_name = os.getenv("LOCATION_PLACE_INDEX_NAME", "").strip() or None
        raw_claim_timeout = os.getenv("AI_PROCESSING_CLAIM_TIMEOUT_SECONDS", "300").strip()
        try:
            self.ai_processing_claim_timeout_seconds = max(1, int(raw_claim_timeout))
        except ValueError:
            self.ai_processing_claim_timeout_seconds = 300

        self.duplicate_distance_threshold_m = self._float_setting(
            "DUPLICATE_DISTANCE_THRESHOLD_M",
            default=100.0,
            minimum=1.0,
        )
        self.duplicate_min_score = self._float_setting(
            "DUPLICATE_MIN_SCORE",
            default=0.4,
            minimum=0.0,
            maximum=1.0,
        )
        self.duplicate_same_category_weight = self._float_setting(
            "DUPLICATE_SAME_CATEGORY_WEIGHT",
            default=1.0,
            minimum=0.0,
            maximum=1.0,
        )
        self.duplicate_similar_category_weight = self._float_setting(
            "DUPLICATE_SIMILAR_CATEGORY_WEIGHT",
            default=0.7,
            minimum=0.0,
            maximum=1.0,
        )

        # Staff auth (issue #72). Defaults match the admin Vite demo credentials
        # so local/CI work out of the box; override in real environments.
        self.secret_key = os.getenv("SECRET_KEY", "").strip() or None
        self.staff_username = os.getenv("STAFF_USERNAME", "staff").strip() or "staff"
        self.staff_password = (
            os.getenv("STAFF_PASSWORD", "staff-demo-password").strip() or "staff-demo-password"
        )
        raw_token_ttl = os.getenv("STAFF_TOKEN_TTL_SECONDS", "43200").strip()
        try:
            self.staff_token_ttl_seconds = max(60, int(raw_token_ttl))
        except ValueError:
            self.staff_token_ttl_seconds = 43200

    @staticmethod
    def _float_setting(
        name: str,
        *,
        default: float,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> float:
        raw = os.getenv(name, str(default)).strip()
        try:
            value = float(raw)
        except ValueError:
            return default
        if minimum is not None:
            value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    @property
    def use_dynamodb(self) -> bool:
        return self.database_backend == "dynamodb"


@lru_cache
def get_settings() -> Settings:
    return Settings()
