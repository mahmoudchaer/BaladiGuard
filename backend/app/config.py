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
        # APP_ENV preferred; ENVIRONMENT accepted as an alias (issue #147).
        raw_env = (
            os.getenv("APP_ENV", "").strip() or os.getenv("ENVIRONMENT", "").strip() or "local"
        )
        self.app_env = raw_env.lower()
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
        # mock = log-only delivery; real = provider path (unconfigured until SNS/SES).
        self.notification_adapter = (
            os.getenv("NOTIFICATION_ADAPTER", "mock").strip().lower() or "mock"
        )
        # Used by auth/signing once #72 lands; validated for production in #147.
        self.secret_key = os.getenv("SECRET_KEY", "").strip() or None
        self.log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"

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
