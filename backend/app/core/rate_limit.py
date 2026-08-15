"""Shared API rate limiting and abuse protection (issues #146 / #186).

Memory backend is used for local/CI ``DATABASE_BACKEND=memory``. Production
DynamoDB deployments share fixed-window counters across workers/instances.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import time
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.core.errors import build_error_response, get_request_id
from app.core.metrics import emit_metric

logger = logging.getLogger(__name__)

_SMOKE_HEADER = "x-baladiguard-smoke-token"
_CLIENT_IDENTITY_RE = re.compile(r"^[A-Za-z0-9:._\-]{1,128}$")


@dataclass(frozen=True)
class RateLimitPolicy:
    name: str
    limit: int
    window_seconds: int


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int


@dataclass
class _Bucket:
    count: int
    reset_at: float


class RateLimiter(Protocol):
    def check(
        self,
        *,
        policy: RateLimitPolicy,
        client_key: str,
        now: float | None = None,
    ) -> RateLimitDecision: ...

    def reset(self) -> None: ...


class InMemoryRateLimiter:
    """Aligned fixed-window limiter for single-process local/CI use."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._buckets: dict[tuple[str, str, int], _Bucket] = {}

    def check(
        self,
        *,
        policy: RateLimitPolicy,
        client_key: str,
        now: float | None = None,
    ) -> RateLimitDecision:
        current_time = time.time() if now is None else now
        window_start = int(current_time // policy.window_seconds) * policy.window_seconds
        reset_at = float(window_start + policy.window_seconds)
        bucket_key = (policy.name, client_key, window_start)

        with self._lock:
            self._prune_expired(current_time)
            bucket = self._buckets.get(bucket_key)
            if bucket is None:
                self._buckets[bucket_key] = _Bucket(count=1, reset_at=reset_at)
                return RateLimitDecision(allowed=True, retry_after_seconds=0)

            if bucket.count >= policy.limit:
                retry_after = max(1, int(bucket.reset_at - current_time))
                return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)

            bucket.count += 1
            return RateLimitDecision(allowed=True, retry_after_seconds=0)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

    def _prune_expired(self, current_time: float) -> None:
        expired_keys = [
            bucket_key
            for bucket_key, bucket in self._buckets.items()
            if current_time >= bucket.reset_at
        ]
        for bucket_key in expired_keys:
            del self._buckets[bucket_key]


_limiter: RateLimiter | None = None


def get_rate_limiter(settings: Settings | None = None) -> RateLimiter:
    """Return the process rate limiter, creating it from current settings."""
    global _limiter
    if _limiter is None:
        cfg = settings or get_settings()
        if cfg.use_dynamodb:
            from app.database.dynamo_rate_limiter import DynamoRateLimiter

            _limiter = DynamoRateLimiter(cfg)
        else:
            _limiter = InMemoryRateLimiter()
    return _limiter


def clear_rate_limiter_cache() -> None:
    """Drop the cached limiter instance (tests / settings changes).

    Does not call backend ``reset()`` — Dynamo reset requires a live table and
    must not run after moto/AWS mocks have torn down.
    """
    global _limiter
    _limiter = None


class _LegacyLimiterProxy:
    """Compatibility shim for older imports of ``public_ticket_rate_limiter``."""

    def check(
        self,
        *,
        policy: RateLimitPolicy,
        client_key: str,
        now: float | None = None,
    ) -> RateLimitDecision:
        return get_rate_limiter().check(policy=policy, client_key=client_key, now=now)

    def reset(self) -> None:
        limiter = _limiter
        if isinstance(limiter, InMemoryRateLimiter):
            limiter.reset()
        clear_rate_limiter_cache()


public_ticket_rate_limiter = _LegacyLimiterProxy()


def build_rate_limit_policies(settings: Settings | None = None) -> dict[str, RateLimitPolicy]:
    """Build env-configurable policies. Keys are stable policy names."""
    cfg = settings or get_settings()
    return {
        "public-ticket-submission": RateLimitPolicy(
            name="public-ticket-submission",
            limit=cfg.rate_limit_ticket_submit_limit,
            window_seconds=cfg.rate_limit_ticket_submit_window_seconds,
        ),
        "public-ticket-tracking": RateLimitPolicy(
            name="public-ticket-tracking",
            limit=cfg.rate_limit_ticket_track_limit,
            window_seconds=cfg.rate_limit_ticket_track_window_seconds,
        ),
        "public-ticket-browsing": RateLimitPolicy(
            name="public-ticket-browsing",
            limit=cfg.rate_limit_ticket_track_limit,
            window_seconds=cfg.rate_limit_ticket_track_window_seconds,
        ),
        "public-upload-report-photo": RateLimitPolicy(
            name="public-upload-report-photo",
            limit=cfg.rate_limit_upload_limit,
            window_seconds=cfg.rate_limit_upload_window_seconds,
        ),
        "public-location-validate": RateLimitPolicy(
            name="public-location-validate",
            limit=cfg.rate_limit_location_validate_limit,
            window_seconds=cfg.rate_limit_location_validate_window_seconds,
        ),
        "staff-login": RateLimitPolicy(
            name="staff-login",
            limit=cfg.rate_limit_staff_login_limit,
            window_seconds=cfg.rate_limit_staff_login_window_seconds,
        ),
        "staff-assistant-query": RateLimitPolicy(
            name="staff-assistant-query",
            limit=cfg.rate_limit_staff_assistant_limit,
            window_seconds=cfg.rate_limit_staff_assistant_window_seconds,
        ),
        "staff-search": RateLimitPolicy(
            name="staff-search",
            limit=cfg.rate_limit_staff_search_limit,
            window_seconds=cfg.rate_limit_staff_search_window_seconds,
        ),
        "staff-password-reset-request": RateLimitPolicy(
            name="staff-password-reset-request",
            limit=cfg.rate_limit_staff_login_limit,
            window_seconds=cfg.rate_limit_staff_login_window_seconds,
        ),
        "staff-password-reset-confirm": RateLimitPolicy(
            name="staff-password-reset-confirm",
            limit=max(cfg.rate_limit_staff_login_limit, 20),
            window_seconds=cfg.rate_limit_staff_login_window_seconds,
        ),
        # Reserved for citizen OTP HTTP routes (#170); documented for Sprint 6.
        "citizen-otp-request": RateLimitPolicy(
            name="citizen-otp-request",
            limit=cfg.rate_limit_citizen_otp_request_limit,
            window_seconds=cfg.rate_limit_citizen_otp_request_window_seconds,
        ),
        "citizen-otp-verify": RateLimitPolicy(
            name="citizen-otp-verify",
            limit=cfg.rate_limit_citizen_otp_verify_limit,
            window_seconds=cfg.rate_limit_citizen_otp_verify_window_seconds,
        ),
    }


# Module-level defaults for import-site monkeypatching in older tests.
PUBLIC_TICKET_SUBMISSION_POLICY = RateLimitPolicy(
    name="public-ticket-submission",
    limit=20,
    window_seconds=60,
)
PUBLIC_TICKET_TRACKING_POLICY = RateLimitPolicy(
    name="public-ticket-tracking",
    limit=60,
    window_seconds=60,
)


def get_client_rate_limit_key(
    request: Request,
    *,
    trust_x_forwarded_for: bool | None = None,
) -> str:
    """Derive a raw client identity for rate limiting.

    When ``TRUST_X_FORWARDED_FOR`` is false (default), forged ``X-Forwarded-For``
    headers are ignored. When true, the leftmost hop is used — only safe behind a
    trusted proxy/gateway that overwrites client-supplied XFF.
    """
    should_trust_xff = (
        get_settings().trust_x_forwarded_for
        if trust_x_forwarded_for is None
        else trust_x_forwarded_for
    )
    forwarded_for = request.headers.get("x-forwarded-for")
    if should_trust_xff and forwarded_for:
        candidate = forwarded_for.split(",", maxsplit=1)[0].strip()
        if candidate and _CLIENT_IDENTITY_RE.fullmatch(candidate):
            return candidate

    if request.client and request.client.host:
        host = request.client.host.strip()
        if host:
            return host

    return "unknown"


def hash_rate_limit_client_key(client_identity: str, *, settings: Settings | None = None) -> str:
    """Hash client identity for storage/logs so raw IPs are not persisted."""
    cfg = settings or get_settings()
    secret_bytes = (cfg.secret_key or "baladiguard-rate-limit-dev").encode("utf-8")
    return hmac.new(
        secret_bytes,
        client_identity.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _is_smoke_request(request: Request, settings: Settings) -> bool:
    token = settings.rate_limit_smoke_bypass_token
    if not token:
        return False
    provided = request.headers.get(_SMOKE_HEADER, "")
    if not provided:
        return False
    return secrets.compare_digest(provided, token)


def rate_limit_response(
    request: Request,
    retry_after_seconds: int,
    *,
    message: str = "Too many requests. Please wait before trying again.",
) -> JSONResponse:
    response = build_error_response(
        code="RATE_LIMIT_EXCEEDED",
        message=message,
        request_id=get_request_id(request),
        status_code=429,
    )
    response.headers["Retry-After"] = str(max(1, int(retry_after_seconds)))
    return response


def enforce_rate_limit(
    request: Request,
    policy_name: str,
    *,
    settings: Settings | None = None,
    message: str | None = None,
    extra_identity: str | None = None,
) -> JSONResponse | None:
    """Check the named policy; return a 429 response when exceeded, else None."""
    cfg = settings or get_settings()
    policies = build_rate_limit_policies(cfg)
    policy = policies.get(policy_name)
    if policy is None:
        raise ValueError(f"Unknown rate limit policy: {policy_name}")

    identity = get_client_rate_limit_key(request)
    if extra_identity:
        identity = f"{identity}:{extra_identity}"

    if _is_smoke_request(request, cfg):
        # Controlled smoke path: higher quota, still enforced (never a global disable).
        policy = RateLimitPolicy(
            name=f"{policy.name}:smoke",
            limit=max(policy.limit, cfg.rate_limit_smoke_limit),
            window_seconds=policy.window_seconds,
        )
        identity = f"smoke:{identity}"

    client_key = hash_rate_limit_client_key(identity, settings=cfg)
    decision = get_rate_limiter(cfg).check(policy=policy, client_key=client_key)
    if decision.allowed:
        return None

    logger.warning(
        "rate_limit_exceeded policy=%s retry_after=%s client_key_fp=%s request_id=%s",
        policy.name,
        decision.retry_after_seconds,
        client_key[:16],
        get_request_id(request),
    )
    emit_metric("RateLimitExceeded", dimensions={"policy": policy.name})
    return rate_limit_response(
        request,
        decision.retry_after_seconds,
        message=message or "Too many requests. Please wait before trying again.",
    )
