from copy import deepcopy

from app.api import tickets as tickets_api
from app.core.rate_limit import InMemoryRateLimiter, RateLimitPolicy
from tests.test_read_tickets import create_ticket
from tests.test_submit_ticket import VALID_PAYLOAD


def test_rate_limiter_allows_until_limit_then_resets_after_window():
    limiter = InMemoryRateLimiter()
    policy = RateLimitPolicy(name="test-policy", limit=2, window_seconds=10)

    assert limiter.check(policy=policy, client_key="client-1", now=100.0).allowed
    assert limiter.check(policy=policy, client_key="client-1", now=101.0).allowed

    rejected = limiter.check(policy=policy, client_key="client-1", now=102.0)

    assert not rejected.allowed
    assert rejected.retry_after_seconds == 8
    assert limiter.check(policy=policy, client_key="client-1", now=111.0).allowed


def test_public_ticket_submission_rejects_burst_with_clear_response(client, monkeypatch):
    monkeypatch.setattr(
        tickets_api,
        "PUBLIC_TICKET_SUBMISSION_POLICY",
        RateLimitPolicy(name="test-public-ticket-submission", limit=2, window_seconds=60),
    )

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
    monkeypatch.setattr(
        tickets_api,
        "PUBLIC_TICKET_TRACKING_POLICY",
        RateLimitPolicy(name="test-public-ticket-tracking", limit=2, window_seconds=60),
    )

    track_path = f"/v1/tickets/track/{created['trackingCode']}"
    assert client.get(track_path).status_code == 200
    assert client.get(track_path).status_code == 200

    response = client.get(track_path)

    assert response.status_code == 429
    assert 1 <= int(response.headers["Retry-After"]) <= 60
    assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    staff_response = client.get("/v1/tickets")

    assert staff_response.status_code == 200
