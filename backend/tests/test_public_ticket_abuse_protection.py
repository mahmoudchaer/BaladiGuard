from copy import deepcopy
from types import SimpleNamespace

from app.core.rate_limit import InMemoryRateLimiter, RateLimitPolicy, get_client_rate_limit_key
from tests.test_read_tickets import create_ticket
from tests.test_submit_ticket import VALID_PAYLOAD


def make_request(headers: dict[str, str] | None = None, client_host: str | None = "10.0.0.9"):
    client = SimpleNamespace(host=client_host) if client_host is not None else None
    return SimpleNamespace(headers=headers or {}, client=client)


def test_rate_limiter_allows_until_limit_then_resets_after_window():
    limiter = InMemoryRateLimiter()
    policy = RateLimitPolicy(name="test-policy", limit=2, window_seconds=10)

    assert limiter.check(policy=policy, client_key="client-1", now=100.0).allowed
    assert limiter.check(policy=policy, client_key="client-1", now=101.0).allowed

    rejected = limiter.check(policy=policy, client_key="client-1", now=102.0)

    assert not rejected.allowed
    assert rejected.retry_after_seconds == 8
    assert limiter.check(policy=policy, client_key="client-1", now=111.0).allowed


def test_rate_limiter_isolates_clients_and_policies():
    limiter = InMemoryRateLimiter()
    submission_policy = RateLimitPolicy(name="submission", limit=1, window_seconds=10)
    tracking_policy = RateLimitPolicy(name="tracking", limit=1, window_seconds=10)

    assert limiter.check(policy=submission_policy, client_key="client-1", now=100.0).allowed
    assert not limiter.check(policy=submission_policy, client_key="client-1", now=101.0).allowed

    assert limiter.check(policy=submission_policy, client_key="client-2", now=102.0).allowed
    assert limiter.check(policy=tracking_policy, client_key="client-1", now=103.0).allowed


def test_rate_limiter_prunes_expired_buckets_for_other_clients():
    limiter = InMemoryRateLimiter()
    policy = RateLimitPolicy(name="test-policy", limit=1, window_seconds=10)

    assert limiter.check(policy=policy, client_key="client-1", now=100.0).allowed
    assert limiter.check(policy=policy, client_key="client-2", now=111.0).allowed

    assert ("test-policy", "client-1", 100) not in limiter._buckets
    assert ("test-policy", "client-2", 110) in limiter._buckets


def test_client_rate_limit_key_uses_direct_client_host_by_default():
    request = make_request(
        headers={"x-forwarded-for": "203.0.113.10, 198.51.100.4"},
        client_host="10.0.0.9",
    )

    assert get_client_rate_limit_key(request) == "10.0.0.9"


def test_client_rate_limit_key_can_trust_forwarded_for_first_hop():
    request = make_request(
        headers={"x-forwarded-for": "203.0.113.10, 198.51.100.4"},
        client_host="10.0.0.9",
    )

    assert get_client_rate_limit_key(request, trust_x_forwarded_for=True) == "203.0.113.10"


def test_client_rate_limit_key_rejects_malformed_forwarded_for_when_trusted():
    request = make_request(
        headers={"x-forwarded-for": "not a valid ip!!!"},
        client_host="10.0.0.9",
    )

    assert get_client_rate_limit_key(request, trust_x_forwarded_for=True) == "10.0.0.9"


def test_public_ticket_submission_rejects_burst_with_clear_response(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_TICKET_SUBMIT_LIMIT", "2")
    monkeypatch.setenv("RATE_LIMIT_TICKET_SUBMIT_WINDOW_SECONDS", "60")
    from app.config import get_settings
    from app.core.rate_limit import clear_rate_limiter_cache

    get_settings.cache_clear()
    clear_rate_limiter_cache()

    assert client.post("/v1/tickets", json=deepcopy(VALID_PAYLOAD)).status_code == 201
    assert client.post("/v1/tickets", json=deepcopy(VALID_PAYLOAD)).status_code == 201

    response = client.post("/v1/tickets", json=deepcopy(VALID_PAYLOAD))

    assert response.status_code == 429
    assert 1 <= int(response.headers["Retry-After"]) <= 60
    body = response.json()
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert (
        body["error"]["message"]
        == "Too many public ticket requests. Please wait before trying again."
    )
    assert "requestId" in body["error"]


def test_public_tracking_lookup_rejects_burst_without_blocking_staff_endpoints(
    client,
    monkeypatch,
):
    created = create_ticket(client)
    monkeypatch.setenv("RATE_LIMIT_TICKET_TRACK_LIMIT", "2")
    monkeypatch.setenv("RATE_LIMIT_TICKET_TRACK_WINDOW_SECONDS", "60")
    from app.config import get_settings
    from app.core.rate_limit import clear_rate_limiter_cache

    get_settings.cache_clear()
    clear_rate_limiter_cache()

    track_path = f"/v1/tickets/track/{created['trackingCode']}"
    assert client.get(track_path).status_code == 200
    assert client.get(track_path).status_code == 200

    response = client.get(track_path)

    assert response.status_code == 429
    assert 1 <= int(response.headers["Retry-After"]) <= 60
    assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    staff_response = client.get("/v1/tickets")

    assert staff_response.status_code == 200
