import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


def load_environment() -> None:
    load_dotenv(BACKEND_DIR / ".env", override=False)
    load_dotenv(REPO_ROOT / ".env", override=False)


load_environment()


class Settings:
    def __init__(self) -> None:
        # APP_ENV preferred; ENVIRONMENT accepted as an alias (issue #147).
        # Keep aliases in sync with app.core.config_validation._ENV_ALIASES.
        raw_env = (
            os.getenv("APP_ENV", "").strip() or os.getenv("ENVIRONMENT", "").strip() or "local"
        ).lower()
        _env_aliases = {
            "prod": "production",
            "prd": "production",
            "dev": "development",
            "develop": "development",
        }
        self.app_env = _env_aliases.get(raw_env, raw_env)
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
        # mock = log-only delivery; real = SES email + SNS SMS (issue #183).
        self.notification_adapter = (
            os.getenv("NOTIFICATION_ADAPTER", "mock").strip().lower() or "mock"
        )
        self.ses_from_email = os.getenv("SES_FROM_EMAIL", "").strip() or None
        self.ses_configuration_set = os.getenv("SES_CONFIGURATION_SET", "").strip() or None
        self.sns_sms_sender_id = os.getenv("SNS_SMS_SENDER_ID", "").strip() or None
        # When true, real adapter may send SMS-only without SES_FROM_EMAIL configured.
        self.notification_allow_sms_only_real = (
            os.getenv("NOTIFICATION_ALLOW_SMS_ONLY_REAL", "true").strip().lower() == "true"
        )
        sandbox_raw = os.getenv("NOTIFICATION_SANDBOX", "").strip().lower()
        if sandbox_raw in {"true", "false"}:
            self.notification_sandbox = sandbox_raw == "true"
        else:
            # Local/dev sandbox by default so real credentials cannot spam citizens.
            self.notification_sandbox = self.app_env in {"local", "test", "development"}
        self.notification_allowlist_emails = frozenset(
            value.strip().lower()
            for value in os.getenv("NOTIFICATION_ALLOWLIST_EMAILS", "").split(",")
            if value.strip()
        )
        self.notification_allowlist_phones = frozenset(
            value.strip()
            for value in os.getenv("NOTIFICATION_ALLOWLIST_PHONES", "").split(",")
            if value.strip()
        )
        self.notification_destination_rate_limit = self._int_setting(
            "NOTIFICATION_DESTINATION_RATE_LIMIT", default=10, minimum=1
        )
        self.notification_destination_rate_window_seconds = self._int_setting(
            "NOTIFICATION_DESTINATION_RATE_WINDOW_SECONDS", default=60, minimum=1
        )
        self.trust_x_forwarded_for = (
            os.getenv("TRUST_X_FORWARDED_FOR", "false").strip().lower() == "true"
        )
        # Shared rate limiting (issue #186). Limits are enforced in-process for
        # memory backends and via DynamoDB ``rate-limit-buckets`` when using DynamoDB.
        self.rate_limit_ticket_submit_limit = self._int_setting(
            "RATE_LIMIT_TICKET_SUBMIT_LIMIT", default=20, minimum=1
        )
        self.rate_limit_ticket_submit_window_seconds = self._int_setting(
            "RATE_LIMIT_TICKET_SUBMIT_WINDOW_SECONDS", default=60, minimum=1
        )
        self.rate_limit_ticket_track_limit = self._int_setting(
            "RATE_LIMIT_TICKET_TRACK_LIMIT", default=60, minimum=1
        )
        self.rate_limit_ticket_track_window_seconds = self._int_setting(
            "RATE_LIMIT_TICKET_TRACK_WINDOW_SECONDS", default=60, minimum=1
        )
        self.rate_limit_upload_limit = self._int_setting(
            "RATE_LIMIT_UPLOAD_LIMIT", default=10, minimum=1
        )
        self.rate_limit_upload_window_seconds = self._int_setting(
            "RATE_LIMIT_UPLOAD_WINDOW_SECONDS", default=60, minimum=1
        )
        self.rate_limit_location_validate_limit = self._int_setting(
            "RATE_LIMIT_LOCATION_VALIDATE_LIMIT", default=30, minimum=1
        )
        self.rate_limit_location_validate_window_seconds = self._int_setting(
            "RATE_LIMIT_LOCATION_VALIDATE_WINDOW_SECONDS", default=60, minimum=1
        )
        self.rate_limit_staff_login_limit = self._int_setting(
            "RATE_LIMIT_STAFF_LOGIN_LIMIT", default=10, minimum=1
        )
        self.rate_limit_staff_login_window_seconds = self._int_setting(
            "RATE_LIMIT_STAFF_LOGIN_WINDOW_SECONDS", default=300, minimum=1
        )
        self.rate_limit_citizen_otp_request_limit = self._int_setting(
            "RATE_LIMIT_CITIZEN_OTP_REQUEST_LIMIT", default=5, minimum=1
        )
        self.rate_limit_citizen_otp_request_window_seconds = self._int_setting(
            "RATE_LIMIT_CITIZEN_OTP_REQUEST_WINDOW_SECONDS", default=300, minimum=1
        )
        self.rate_limit_citizen_otp_verify_limit = self._int_setting(
            "RATE_LIMIT_CITIZEN_OTP_VERIFY_LIMIT", default=10, minimum=1
        )
        self.rate_limit_citizen_otp_verify_window_seconds = self._int_setting(
            "RATE_LIMIT_CITIZEN_OTP_VERIFY_WINDOW_SECONDS", default=300, minimum=1
        )
        # Optional smoke-test token: raises the matched client's quota, never disables limits.
        self.rate_limit_smoke_bypass_token = (
            os.getenv("RATE_LIMIT_SMOKE_BYPASS_TOKEN", "").strip() or None
        )
        self.rate_limit_smoke_limit = self._int_setting(
            "RATE_LIMIT_SMOKE_LIMIT", default=1000, minimum=1
        )
        self.log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"

        # Staff auth (issue #175). Individual staff accounts are persisted;
        # DEMO_STAFF_PASSWORD is only used when bootstrapping local/test seed
        # accounts. Shared env-credential login has been removed.
        # SECRET_KEY is also validated for production in issue #147.
        self.secret_key = os.getenv("SECRET_KEY", "").strip() or None
        # Legacy aliases kept for local .env compatibility when seeding demos.
        legacy_staff_password = os.getenv("STAFF_PASSWORD", "").strip()
        self.demo_staff_password = (
            os.getenv("DEMO_STAFF_PASSWORD", "").strip()
            or legacy_staff_password
            or "staff-demo-password"
        )
        # Deprecated no-ops retained so older .env files do not break startup.
        self.staff_username = os.getenv("STAFF_USERNAME", "staff").strip() or "staff"
        self.staff_password = self.demo_staff_password
        seed_demo_raw = os.getenv("SEED_DEMO_STAFF", "").strip().lower()
        if seed_demo_raw in {"true", "false"}:
            self.seed_demo_staff = seed_demo_raw == "true"
        else:
            # Default on for local/test/development; off for production/staging.
            self.seed_demo_staff = self.app_env in {"local", "test", "development"}
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

    @staticmethod
    def _int_setting(name: str, *, default: int, minimum: int = 1) -> int:
        raw = os.getenv(name, str(default)).strip()
        try:
            value = int(raw)
        except ValueError:
            return default
        return max(minimum, value)

    @property
    def use_dynamodb(self) -> bool:
        return self.database_backend == "dynamodb"


@lru_cache
def get_settings() -> Settings:
    return Settings()
