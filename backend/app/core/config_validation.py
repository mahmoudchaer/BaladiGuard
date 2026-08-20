"""Startup and health configuration validation (issue #147).

Production must not silently use development-only defaults for secrets,
persistence, or authentication-related settings. Local/development remain
usable with documented defaults. Secret *values* are never included in
issue messages, logs from this module, or health payloads.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from app.config import Settings, get_settings

AllowedSeverity = Literal["error", "warning"]

ALLOWED_ENVIRONMENTS = frozenset({"local", "development", "staging", "production", "test"})
# Deployed envs: no silent localhost citizen deep-link defaults (issue #257).
_DEPLOYED_ENVIRONMENTS_REQUIRING_CITIZEN_APP_BASE = frozenset({"staging", "production"})
ALLOWED_DATABASE_BACKENDS = frozenset({"memory", "dynamodb"})
ALLOWED_NOTIFICATION_ADAPTERS = frozenset({"mock", "real"})
ALLOWED_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})

# Common typos / short forms normalize before validation and production checks.
_ENV_ALIASES = {
    "prod": "production",
    "prd": "production",
    "dev": "development",
    "develop": "development",
}

# Known-unsafe placeholders — compared only, never echoed back.
_UNSAFE_SECRET_PLACEHOLDERS = frozenset(
    {
        "",
        "changeme",
        "change-me",
        "change_me",
        "secret",
        "password",
        "dev",
        "test",
        "your-secret-key",
        "baladiguard-dev-secret-change-me",
    }
)

_LOCALHOST_MARKERS = ("localhost", "127.0.0.1", "0.0.0.0")


@dataclass(frozen=True, slots=True)
class ConfigIssue:
    code: str
    message: str
    severity: AllowedSeverity = "error"


@dataclass(slots=True)
class ConfigValidationResult:
    env: str
    issues: list[ConfigIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def should_abort_startup(self) -> bool:
        """Fail closed for deployed misconfig and unknown environments.

        Invalid ``APP_ENV`` values must abort so a deploy typo cannot bypass
        fail-closed checks. ``production`` and ``staging`` abort on any error
        severity issue (including missing citizen deep-link base URL). Local /
        development / test keep starting with soft defaults when formats are
        otherwise valid.
        """
        if any(issue.code == "INVALID_APP_ENV" for issue in self.issues):
            return True
        return self.env in _DEPLOYED_ENVIRONMENTS_REQUIRING_CITIZEN_APP_BASE and not self.ok

    def to_health_dict(self) -> dict[str, Any]:
        return {
            "status": "ok" if self.ok else "error",
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "severity": issue.severity,
                }
                for issue in self.issues
            ],
        }


def normalize_app_env(raw: str) -> str:
    """Normalize env labels; apply known aliases before allow-list checks."""
    value = raw.strip().lower() or "local"
    return _ENV_ALIASES.get(value, value)


def resolve_app_env(environ: Mapping[str, str] | None = None) -> str:
    env = environ if environ is not None else os.environ
    raw = (env.get("APP_ENV") or env.get("ENVIRONMENT") or "local").strip().lower()
    return normalize_app_env(raw or "local")


def _raw(env: Mapping[str, str], name: str) -> str | None:
    if name not in env:
        return None
    return env[name]


def _is_unsafe_secret(value: str | None) -> bool:
    if value is None:
        return True
    return value.strip().lower() in _UNSAFE_SECRET_PLACEHOLDERS


def _looks_like_localhost(url: str) -> bool:
    lowered = url.strip().lower()
    return any(marker in lowered for marker in _LOCALHOST_MARKERS)


def validate_configuration(
    settings: Settings | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> ConfigValidationResult:
    """Validate formats always; enforce production hard-fail rules for unsafe defaults."""
    env_map: Mapping[str, str] = environ if environ is not None else os.environ
    cfg = settings or get_settings()
    app_env = resolve_app_env(env_map)
    result = ConfigValidationResult(env=app_env)

    if app_env not in ALLOWED_ENVIRONMENTS:
        result.issues.append(
            ConfigIssue(
                code="INVALID_APP_ENV",
                message=(
                    "APP_ENV/ENVIRONMENT must be one of: "
                    + ", ".join(sorted(ALLOWED_ENVIRONMENTS))
                    + "."
                ),
            )
        )

    raw_backend = _raw(env_map, "DATABASE_BACKEND")
    if raw_backend is not None:
        normalized_backend = raw_backend.strip().lower()
        if normalized_backend not in ALLOWED_DATABASE_BACKENDS:
            result.issues.append(
                ConfigIssue(
                    code="INVALID_DATABASE_BACKEND",
                    message="DATABASE_BACKEND must be 'memory' or 'dynamodb'.",
                )
            )

    raw_adapter = _raw(env_map, "NOTIFICATION_ADAPTER")
    if raw_adapter is not None:
        normalized_adapter = raw_adapter.strip().lower() or "mock"
        if normalized_adapter not in ALLOWED_NOTIFICATION_ADAPTERS:
            result.issues.append(
                ConfigIssue(
                    code="INVALID_NOTIFICATION_ADAPTER",
                    message="NOTIFICATION_ADAPTER must be 'mock' or 'real'.",
                )
            )

    raw_log_level = _raw(env_map, "LOG_LEVEL")
    if raw_log_level is not None and raw_log_level.strip():
        if raw_log_level.strip().upper() not in ALLOWED_LOG_LEVELS:
            result.issues.append(
                ConfigIssue(
                    code="INVALID_LOG_LEVEL",
                    message=(
                        "LOG_LEVEL must be one of: " + ", ".join(sorted(ALLOWED_LOG_LEVELS)) + "."
                    ),
                )
            )

    for name, minimum, maximum in (
        ("DUPLICATE_DISTANCE_THRESHOLD_M", 1.0, None),
        ("DUPLICATE_MIN_SCORE", 0.0, 1.0),
        ("DUPLICATE_SAME_CATEGORY_WEIGHT", 0.0, 1.0),
        ("DUPLICATE_SIMILAR_CATEGORY_WEIGHT", 0.0, 1.0),
        ("MUNICIPALITY_ROUTING_HIGH_CONFIDENCE", 0.5, 1.0),
    ):
        raw = _raw(env_map, name)
        if raw is None or not raw.strip():
            continue
        try:
            value = float(raw.strip())
        except ValueError:
            result.issues.append(
                ConfigIssue(
                    code=f"INVALID_{name}",
                    message=f"{name} must be a number.",
                )
            )
            continue
        if minimum is not None and value < minimum:
            result.issues.append(
                ConfigIssue(
                    code=f"INVALID_{name}",
                    message=f"{name} must be >= {minimum}.",
                )
            )
        if maximum is not None and value > maximum:
            result.issues.append(
                ConfigIssue(
                    code=f"INVALID_{name}",
                    message=f"{name} must be <= {maximum}.",
                )
            )

    raw_claim = _raw(env_map, "AI_PROCESSING_CLAIM_TIMEOUT_SECONDS")
    if raw_claim is not None and raw_claim.strip():
        try:
            claim = int(raw_claim.strip())
            if claim < 1:
                raise ValueError
        except ValueError:
            result.issues.append(
                ConfigIssue(
                    code="INVALID_AI_PROCESSING_CLAIM_TIMEOUT_SECONDS",
                    message="AI_PROCESSING_CLAIM_TIMEOUT_SECONDS must be an integer >= 1.",
                )
            )

    for rate_limit_name in (
        "RATE_LIMIT_TICKET_SUBMIT_LIMIT",
        "RATE_LIMIT_TICKET_SUBMIT_WINDOW_SECONDS",
        "RATE_LIMIT_TICKET_TRACK_LIMIT",
        "RATE_LIMIT_TICKET_TRACK_WINDOW_SECONDS",
        "RATE_LIMIT_UPLOAD_LIMIT",
        "RATE_LIMIT_UPLOAD_WINDOW_SECONDS",
        "RATE_LIMIT_LOCATION_VALIDATE_LIMIT",
        "RATE_LIMIT_LOCATION_VALIDATE_WINDOW_SECONDS",
        "RATE_LIMIT_STAFF_LOGIN_LIMIT",
        "RATE_LIMIT_STAFF_LOGIN_WINDOW_SECONDS",
        "RATE_LIMIT_STAFF_ASSISTANT_LIMIT",
        "RATE_LIMIT_STAFF_ASSISTANT_WINDOW_SECONDS",
        "RATE_LIMIT_STAFF_SEARCH_LIMIT",
        "RATE_LIMIT_STAFF_SEARCH_WINDOW_SECONDS",
        "RATE_LIMIT_CITIZEN_OTP_REQUEST_LIMIT",
        "RATE_LIMIT_CITIZEN_OTP_REQUEST_WINDOW_SECONDS",
        "RATE_LIMIT_CITIZEN_OTP_VERIFY_LIMIT",
        "RATE_LIMIT_CITIZEN_OTP_VERIFY_WINDOW_SECONDS",
        "RATE_LIMIT_SMOKE_LIMIT",
    ):
        raw_rate = _raw(env_map, rate_limit_name)
        if raw_rate is None or not raw_rate.strip():
            continue
        try:
            value = int(raw_rate.strip())
            if value < 1:
                raise ValueError
        except ValueError:
            result.issues.append(
                ConfigIssue(
                    code=f"INVALID_{rate_limit_name}",
                    message=f"{rate_limit_name} must be an integer >= 1.",
                )
            )

    if not cfg.aws_region.strip():
        result.issues.append(
            ConfigIssue(
                code="INVALID_AWS_REGION",
                message="AWS_REGION must be a non-empty region id (for example us-east-1).",
            )
        )

    # Deployed environments share the real integration boundary. Staging is a
    # production rehearsal, not a demo mode: it must never silently select
    # memory persistence, mock providers, sample seeds, or local service endpoints.
    if app_env in _DEPLOYED_ENVIRONMENTS_REQUIRING_CITIZEN_APP_BASE:
        env_label = "Production" if app_env == "production" else "Staging"
        backend = (raw_backend or cfg.database_backend).strip().lower()
        if backend != "dynamodb":
            result.issues.append(
                ConfigIssue(
                    code="UNSAFE_DATABASE_BACKEND",
                    message=(
                        f"{env_label} requires DATABASE_BACKEND=dynamodb "
                        "(memory is development-only)."
                    ),
                )
            )

        adapter = (raw_adapter or cfg.notification_adapter).strip().lower() or "mock"
        if adapter != "real":
            result.issues.append(
                ConfigIssue(
                    code="UNSAFE_NOTIFICATION_ADAPTER",
                    message=(
                        f"{env_label} requires NOTIFICATION_ADAPTER=real "
                        "(mock is development-only)."
                    ),
                )
            )
        elif not str(_raw(env_map, "SES_FROM_EMAIL") or cfg.ses_from_email or "").strip():
            # Email is the primary documented production channel; SMS can run as well.
            result.issues.append(
                ConfigIssue(
                    code="MISSING_SES_FROM_EMAIL",
                    message=(
                        f"{env_label} NOTIFICATION_ADAPTER=real requires SES_FROM_EMAIL "
                        "(verified SES identity)."
                    ),
                )
            )
        if app_env == "production" and cfg.notification_sandbox:
            result.issues.append(
                ConfigIssue(
                    code="UNSAFE_NOTIFICATION_SANDBOX",
                    message=(
                        "Production should set NOTIFICATION_SANDBOX=false after SES/SNS leave "
                        "sandbox and allowlists are no longer required."
                    ),
                    severity="warning",
                )
            )

        secret = _raw(env_map, "SECRET_KEY")
        if secret is None or _is_unsafe_secret(secret):
            result.issues.append(
                ConfigIssue(
                    code="UNSAFE_SECRET_KEY",
                    message=(
                        f"{env_label} requires a non-placeholder SECRET_KEY "
                        "(do not use empty or development defaults)."
                    ),
                )
            )

        # Shared env-credential login was removed in #175. Demo passwords may only
        # be used when explicitly seeding local-style demo staff accounts.
        if cfg.seed_demo_staff:
            demo_password = (
                _raw(env_map, "DEMO_STAFF_PASSWORD")
                or _raw(env_map, "STAFF_PASSWORD")
                or cfg.demo_staff_password
            )
            if (
                demo_password is None
                or demo_password.strip() == ""
                or demo_password.strip() == "staff-demo-password"
            ):
                result.issues.append(
                    ConfigIssue(
                        code="UNSAFE_STAFF_PASSWORD",
                        message=(
                            f"{env_label} must not seed demo staff with the default "
                            "password. Set SEED_DEMO_STAFF=false or provide a strong "
                            "DEMO_STAFF_PASSWORD."
                        ),
                    )
                )

        raw_ttl = _raw(env_map, "STAFF_TOKEN_TTL_SECONDS")
        if raw_ttl is not None and raw_ttl.strip():
            try:
                ttl = int(raw_ttl.strip())
                if ttl < 60:
                    raise ValueError
            except ValueError:
                result.issues.append(
                    ConfigIssue(
                        code="INVALID_STAFF_TOKEN_TTL_SECONDS",
                        message="STAFF_TOKEN_TTL_SECONDS must be an integer >= 60.",
                    )
                )

        if not cfg.location_place_index_name:
            result.issues.append(
                ConfigIssue(
                    code="MISSING_LOCATION_PLACE_INDEX_NAME",
                    message=(
                        f"{env_label} requires LOCATION_PLACE_INDEX_NAME "
                        "(empty falls back to the local Beirut index)."
                    ),
                )
            )

        if not cfg.trust_x_forwarded_for:
            result.issues.append(
                ConfigIssue(
                    code="TRUST_X_FORWARDED_FOR_DISABLED",
                    message=(
                        f"{env_label} is typically behind a trusted proxy/API Gateway. "
                        "Set TRUST_X_FORWARDED_FOR=true only when that edge overwrites "
                        "client-supplied X-Forwarded-For; leave false for direct ingress."
                    ),
                    severity="warning",
                )
            )

        if not cfg.aws_s3_bucket:
            result.issues.append(
                ConfigIssue(
                    code="MISSING_AWS_S3_BUCKET",
                    message=f"{env_label} requires AWS_S3_BUCKET for photo uploads.",
                )
            )

        endpoint = cfg.dynamodb_endpoint_url
        if endpoint and _looks_like_localhost(endpoint):
            result.issues.append(
                ConfigIssue(
                    code="UNSAFE_DYNAMODB_ENDPOINT_URL",
                    message=(
                        f"{env_label} must not use a localhost DynamoDB endpoint "
                        "(leave DYNAMODB_ENDPOINT_URL empty for AWS)."
                    ),
                )
            )

        if cfg.seed_sample_tickets:
            result.issues.append(
                ConfigIssue(
                    code="UNSAFE_SEED_SAMPLE_TICKETS",
                    message=f"{env_label} must set SEED_SAMPLE_TICKETS=false.",
                )
            )

        if cfg.otp_dev_plaintext_stdout:
            result.issues.append(
                ConfigIssue(
                    code="UNSAFE_OTP_DEV_PLAINTEXT_STDOUT",
                    message=(
                        f"{env_label} must set OTP_DEV_PLAINTEXT_STDOUT=false; "
                        "printing OTP codes is development-only."
                    ),
                )
            )

        if not cfg.image_redaction_enabled:
            result.issues.append(
                ConfigIssue(
                    code="UNSAFE_IMAGE_REDACTION_DISABLED",
                    message=f"{env_label} requires IMAGE_REDACTION_ENABLED=true.",
                )
            )
        if cfg.image_redaction_detector != "aws_rekognition":
            result.issues.append(
                ConfigIssue(
                    code="UNSAFE_IMAGE_REDACTION_DETECTOR",
                    message=(
                        f"{env_label} requires IMAGE_REDACTION_DETECTOR=aws_rekognition; "
                        "local/disabled detectors are development-only."
                    ),
                )
            )

    # Citizen app deep links for SMS/email (issue #257). Fail closed for every
    # deployed environment: staging and production require an explicit
    # non-localhost https base (no silent localhost default). Local /
    # development / test may omit CITIZEN_APP_BASE_URL and use localhost.
    if app_env in _DEPLOYED_ENVIRONMENTS_REQUIRING_CITIZEN_APP_BASE:
        from app.services.notifications.deep_links import (
            is_localhost_base_url,
            is_valid_citizen_app_base_url,
            normalize_citizen_app_base_url,
        )

        env_label = "Production" if app_env == "production" else "Staging"
        citizen_base = normalize_citizen_app_base_url(cfg.citizen_app_base_url)
        if not citizen_base:
            result.issues.append(
                ConfigIssue(
                    code="MISSING_CITIZEN_APP_BASE_URL",
                    message=(
                        f"{env_label} requires CITIZEN_APP_BASE_URL "
                        "(HTTPS base for citizen notification deep links)."
                    ),
                )
            )
        elif is_localhost_base_url(citizen_base):
            result.issues.append(
                ConfigIssue(
                    code="UNSAFE_CITIZEN_APP_BASE_URL",
                    message=(f"{env_label} must not use a localhost CITIZEN_APP_BASE_URL."),
                )
            )
        elif not is_valid_citizen_app_base_url(citizen_base, require_https=True):
            result.issues.append(
                ConfigIssue(
                    code="INVALID_CITIZEN_APP_BASE_URL",
                    message=(
                        "CITIZEN_APP_BASE_URL must be a valid https URL "
                        "(no trailing path required; e.g. https://app.example.com)."
                    ),
                )
            )

    # Browser CORS allowlist for admin + citizen-web (issue #263).
    # Staging/production must set CORS_ALLOWED_ORIGINS to explicit non-localhost
    # https origins — never silently keep local Vite/Expo defaults.
    if app_env in _DEPLOYED_ENVIRONMENTS_REQUIRING_CITIZEN_APP_BASE:
        from app.core.cors import is_localhost_origin, parse_cors_allowed_origins

        env_label = "Production" if app_env == "production" else "Staging"
        origins = parse_cors_allowed_origins(cfg.cors_allowed_origins)
        if not origins:
            result.issues.append(
                ConfigIssue(
                    code="MISSING_CORS_ALLOWED_ORIGINS",
                    message=(
                        f"{env_label} requires CORS_ALLOWED_ORIGINS "
                        "(comma-separated https origins for admin and citizen-web)."
                    ),
                )
            )
        else:
            for origin in origins:
                if is_localhost_origin(origin):
                    result.issues.append(
                        ConfigIssue(
                            code="UNSAFE_CORS_ALLOWED_ORIGINS",
                            message=(
                                f"{env_label} must not include localhost origins "
                                "in CORS_ALLOWED_ORIGINS."
                            ),
                        )
                    )
                    break
                if not origin.lower().startswith("https://"):
                    result.issues.append(
                        ConfigIssue(
                            code="INVALID_CORS_ALLOWED_ORIGINS",
                            message=(
                                "CORS_ALLOWED_ORIGINS entries must use https "
                                f"in {app_env} (e.g. https://citizen.example.com)."
                            ),
                        )
                    )
                    break

    return result
