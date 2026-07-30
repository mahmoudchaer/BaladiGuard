from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock

from fastapi import Request

from app.config import get_settings


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


class InMemoryRateLimiter:
    """Simple per-process fixed-window limiter for public endpoint abuse protection."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._buckets: dict[tuple[str, str], _Bucket] = {}

    def check(
        self,
        *,
        policy: RateLimitPolicy,
        client_key: str,
        now: float | None = None,
    ) -> RateLimitDecision:
        current_time = time.monotonic() if now is None else now
        bucket_key = (policy.name, client_key)

        with self._lock:
            self._prune_expired(current_time)
            bucket = self._buckets.get(bucket_key)
            if bucket is None or current_time >= bucket.reset_at:
                self._buckets[bucket_key] = _Bucket(
                    count=1,
                    reset_at=current_time + policy.window_seconds,
                )
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
public_ticket_rate_limiter = InMemoryRateLimiter()


def get_client_rate_limit_key(
    request: Request,
    *,
    trust_x_forwarded_for: bool | None = None,
) -> str:
    should_trust_xff = (
        get_settings().trust_x_forwarded_for
        if trust_x_forwarded_for is None
        else trust_x_forwarded_for
    )
    forwarded_for = request.headers.get("x-forwarded-for")
    if should_trust_xff and forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip() or "unknown"

    if request.client and request.client.host:
        return request.client.host

    return "unknown"
