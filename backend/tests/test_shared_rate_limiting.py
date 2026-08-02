"""Shared / multi-instance rate limiting coverage for issue #186."""

from __future__ import annotations

from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.core.rate_limit import (
    InMemoryRateLimiter,
    RateLimitPolicy,
    build_rate_limit_policies,
    clear_rate_limiter_cache,
    enforce_rate_limit,
    get_rate_limiter,
    hash_rate_limit_client_key,
)
from app.database.dynamo_rate_limiter import DynamoRateLimiter
from app.database.dynamodb_tables import TABLE_DEFINITIONS
from app.main import app
from tests.conftest import contribution_ready_auth_headers
from tests.test_submit_ticket import VALID_PAYLOAD


def test_rate_limit_buckets_table_is_defined() -> None:
    suffixes = {item["suffix"] for item in TABLE_DEFINITIONS}
    assert "rate-limit-buckets" in suffixes


def test_policies_are_environment_configurable(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_TICKET_SUBMIT_LIMIT", "7")
    monkeypatch.setenv("RATE_LIMIT_UPLOAD_LIMIT", "3")
    monkeypatch.setenv("RATE_LIMIT_STAFF_LOGIN_WINDOW_SECONDS", "120")
    get_settings.cache_clear()
    policies = build_rate_limit_policies(Settings())
    assert policies["public-ticket-submission"].limit == 7
    assert policies["public-upload-report-photo"].limit == 3
    assert policies["staff-login"].window_seconds == 120
    assert "citizen-otp-request" in policies
    assert "citizen-otp-verify" in policies
    assert "staff-password-reset-request" in policies
    assert "staff-password-reset-confirm" in policies
    get_settings.cache_clear()


def test_client_key_hash_does_not_embed_raw_identity() -> None:
    hashed = hash_rate_limit_client_key("203.0.113.50")
    assert "203.0.113.50" not in hashed
    assert len(hashed) == 64


def test_dynamo_limiter_is_shared_across_instances(dynamodb_settings: Settings) -> None:
    """Two worker-like limiter instances must share the same Dynamo counters."""
    clear_rate_limiter_cache()
    worker_a = DynamoRateLimiter(dynamodb_settings)
    worker_b = DynamoRateLimiter(dynamodb_settings)
    policy = RateLimitPolicy(name="multi-instance", limit=2, window_seconds=60)
    now = 1_700_000_000.0

    assert worker_a.check(policy=policy, client_key="shared-client", now=now).allowed
    assert worker_b.check(policy=policy, client_key="shared-client", now=now + 1).allowed
    rejected_a = worker_a.check(policy=policy, client_key="shared-client", now=now + 2)
    rejected_b = worker_b.check(policy=policy, client_key="shared-client", now=now + 3)

    assert not rejected_a.allowed
    assert not rejected_b.allowed
    assert rejected_a.retry_after_seconds >= 1


def test_get_rate_limiter_uses_dynamo_when_configured(dynamodb_settings: Settings) -> None:
    clear_rate_limiter_cache()
    limiter = get_rate_limiter(dynamodb_settings)
    assert isinstance(limiter, DynamoRateLimiter)
    clear_rate_limiter_cache()


def test_staff_login_rate_limit_returns_retry_after(
    anonymous_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_STAFF_LOGIN_LIMIT", "2")
    monkeypatch.setenv("RATE_LIMIT_STAFF_LOGIN_WINDOW_SECONDS", "300")
    get_settings.cache_clear()
    clear_rate_limiter_cache()

    payload = {"username": "staff", "password": "wrong-password"}
    assert anonymous_client.post("/v1/staff/login", json=payload).status_code == 401
    assert anonymous_client.post("/v1/staff/login", json=payload).status_code == 401
    response = anonymous_client.post("/v1/staff/login", json=payload)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert 1 <= int(response.headers["Retry-After"]) <= 300

    get_settings.cache_clear()
    clear_rate_limiter_cache()


def test_upload_rate_limit_is_stricter_than_default_submit(
    anonymous_client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_UPLOAD_LIMIT", "2")
    monkeypatch.setenv("RATE_LIMIT_UPLOAD_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    clear_rate_limiter_cache()

    def _post() -> object:
        return anonymous_client.post(
            "/v1/uploads/report-photo",
            files={"file": ("x.jpg", BytesIO(b"not-a-real-image"), "image/jpeg")},
        )

    # Pre-body middleware rate limit; any non-429 counts against the budget.
    assert _post().status_code != 429
    assert _post().status_code != 429
    limited = _post()
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in limited.headers

    get_settings.cache_clear()
    clear_rate_limiter_cache()


def test_location_validate_rate_limit(anonymous_client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_LOCATION_VALIDATE_LIMIT", "2")
    monkeypatch.setenv("RATE_LIMIT_LOCATION_VALIDATE_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    clear_rate_limiter_cache()

    payload = {"latitude": 33.8938, "longitude": 35.5018, "addressText": "Beirut"}
    assert anonymous_client.post("/v1/locations/validate", json=payload).status_code in {
        200,
        400,
        502,
    }
    assert anonymous_client.post("/v1/locations/validate", json=payload).status_code in {
        200,
        400,
        502,
    }
    limited = anonymous_client.post("/v1/locations/validate", json=payload)
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]

    get_settings.cache_clear()
    clear_rate_limiter_cache()


def test_smoke_token_raises_quota_without_disabling_limits(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_TICKET_SUBMIT_LIMIT", "1")
    monkeypatch.setenv("RATE_LIMIT_SMOKE_BYPASS_TOKEN", "smoke-secret")
    monkeypatch.setenv("RATE_LIMIT_SMOKE_LIMIT", "2")
    get_settings.cache_clear()
    clear_rate_limiter_cache()

    client = TestClient(app)
    headers = {
        "X-BaladiGuard-Smoke-Token": "smoke-secret",
        **contribution_ready_auth_headers(),
    }

    assert (
        client.post("/v1/tickets", json=deepcopy(VALID_PAYLOAD), headers=headers).status_code == 201
    )
    assert (
        client.post("/v1/tickets", json=deepcopy(VALID_PAYLOAD), headers=headers).status_code == 201
    )
    limited = client.post("/v1/tickets", json=deepcopy(VALID_PAYLOAD), headers=headers)
    assert limited.status_code == 429

    # Without the token, the normal low limit still applies independently.
    clear_rate_limiter_cache()
    assert (
        client.post(
            "/v1/tickets", json=deepcopy(VALID_PAYLOAD), headers=contribution_ready_auth_headers()
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/v1/tickets", json=deepcopy(VALID_PAYLOAD), headers=contribution_ready_auth_headers()
        ).status_code
        == 429
    )

    get_settings.cache_clear()
    clear_rate_limiter_cache()


def test_enforce_rate_limit_logs_fingerprint_not_raw_ip(monkeypatch, caplog) -> None:
    monkeypatch.setenv("RATE_LIMIT_TICKET_SUBMIT_LIMIT", "1")
    get_settings.cache_clear()
    clear_rate_limiter_cache()

    request = SimpleNamespace(
        headers={},
        client=SimpleNamespace(host="198.51.100.20"),
        state=SimpleNamespace(request_id="req_test"),
    )

    import logging

    with caplog.at_level(logging.WARNING, logger="app.core.rate_limit"):
        assert enforce_rate_limit(request, "public-ticket-submission") is None
        rejected = enforce_rate_limit(request, "public-ticket-submission")

    assert rejected is not None
    assert "198.51.100.20" not in caplog.text
    assert "rate_limit_exceeded" in caplog.text
    assert "client_key_fp=" in caplog.text

    get_settings.cache_clear()
    clear_rate_limiter_cache()


def test_memory_limiter_aligned_windows_match_dynamo_semantics() -> None:
    memory = InMemoryRateLimiter()
    policy = RateLimitPolicy(name="aligned", limit=1, window_seconds=10)
    assert memory.check(policy=policy, client_key="c", now=100.0).allowed
    assert not memory.check(policy=policy, client_key="c", now=109.0).allowed
    assert memory.check(policy=policy, client_key="c", now=110.0).allowed
