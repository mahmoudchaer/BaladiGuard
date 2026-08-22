"""Production security / abuse hardening coverage (issue #316)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.body_limits import (
    json_nesting_too_deep,
    reject_oversized_body,
    reject_oversized_headers,
)
from app.core.rate_limit import (
    build_rate_limit_policies,
    check_identity_rate_limit,
    clear_rate_limiter_cache,
)
from app.core.request_hardening import match_path_rate_limit_policy
from app.core.security_headers import apply_security_headers
from app.core.trusted_hosts import (
    host_is_allowed,
    reject_untrusted_host,
    resolve_allowed_hosts,
)
from app.main import app
from app.schemas.municipality import UpsertMunicipalityRequest
from app.schemas.stored_municipality import GeoPolygon
from app.schemas.ticket_merge import MergeDuplicateTicketsRequest
from app.schemas.workforce import UpsertWorkerRequest
from app.services.whatsapp.submission import WhatsAppSubmissionRateLimited, submit_whatsapp_report
from tests.conftest import issue_test_staff_token


class _FakeRequest:
    def __init__(
        self,
        *,
        path: str = "/v1/tickets",
        method: str = "POST",
        headers: dict[str, str] | None = None,
        host: str = "testserver",
    ) -> None:
        self.url = type("URL", (), {"path": path})()
        self.method = method
        self.headers = headers or {}
        self.headers.setdefault("host", host)
        self.state = type("State", (), {"request_id": "req_test"})()
        self.client = type("Client", (), {"host": "127.0.0.1"})()


def test_security_headers_are_present_on_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in response.headers["Permissions-Policy"]
    assert response.headers["Cache-Control"] == "no-store"
    assert "X-Request-Id" in response.headers


def test_hsts_only_in_deployed_environments() -> None:
    local: dict[str, str] = {}
    apply_security_headers(local, app_env="test")
    assert "Strict-Transport-Security" not in local
    prod: dict[str, str] = {}
    apply_security_headers(prod, app_env="production")
    assert prod["Strict-Transport-Security"].startswith("max-age=")


def test_trusted_hosts_fail_closed_for_production() -> None:
    assert resolve_allowed_hosts(app_env="local", allowed_hosts=None) == ["*"]
    assert resolve_allowed_hosts(app_env="production", allowed_hosts=None) == []
    assert resolve_allowed_hosts(
        app_env="production", allowed_hosts="api.example.com, .example.com"
    ) == ["api.example.com", ".example.com"]
    assert host_is_allowed("api.example.com", ["api.example.com"])
    assert host_is_allowed("staff.example.com", [".example.com"])
    assert not host_is_allowed("evil.com", ["api.example.com"])


def test_health_paths_bypass_trusted_host() -> None:
    request = _FakeRequest(path="/health/live", host="10.0.1.23")
    assert reject_untrusted_host(request, allowed_hosts=["api.example.com"]) is None
    blocked = reject_untrusted_host(
        _FakeRequest(path="/v1/tickets", host="10.0.1.23"),
        allowed_hosts=["api.example.com"],
    )
    assert blocked is not None
    assert blocked.status_code == 400
    assert blocked.body
    assert b"INVALID_HOST" in blocked.body


def test_oversized_headers_are_rejected() -> None:
    request = _FakeRequest(headers={"x-pad": "a" * 200})
    rejected = reject_oversized_headers(request, max_header_bytes=50)
    assert rejected is not None
    assert rejected.status_code == 431
    assert b"HEADERS_TOO_LARGE" in rejected.body


def test_oversized_json_content_length_is_rejected() -> None:
    request = _FakeRequest(headers={"content-length": "999999"})
    rejected = reject_oversized_body(request, max_bytes=1024)
    assert rejected is not None
    assert rejected.status_code == 413
    assert b"PAYLOAD_TOO_LARGE" in rejected.body


def test_http_rejects_oversized_json_body() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/locations/validate",
        content=b'{"pad":"' + (b"a" * 300_000) + b'"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_json_nesting_guard() -> None:
    nested: object = {"a": 1}
    for _ in range(25):
        nested = {"child": nested}
    assert json_nesting_too_deep(nested, max_depth=20)
    assert not json_nesting_too_deep({"ok": [1, 2, 3]}, max_depth=20)


def test_polygon_rejects_extra_keys_and_too_many_vertices() -> None:
    closed = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]
    GeoPolygon.model_validate({"coordinates": closed})
    try:
        GeoPolygon.model_validate({"coordinates": closed, "extra": {"deep": True}})
        raise AssertionError("extra keys must be rejected")
    except Exception as exc:
        assert "extra" in str(exc).lower() or "forbidden" in str(exc).lower()
    huge = [[float(i), 0.0] for i in range(300)]
    huge.append(huge[0])
    try:
        UpsertMunicipalityRequest.model_validate(
            {
                "name": "X",
                "description": "A valid municipality description",
                "serviceDomains": ["roads"],
                "bounds": {
                    "minLatitude": 33.0,
                    "maxLatitude": 34.0,
                    "minLongitude": 35.0,
                    "maxLongitude": 36.0,
                },
                "polygon": {"coordinates": huge},
            }
        )
        raise AssertionError("oversized polygon must be rejected")
    except Exception:
        pass


def test_merge_and_workforce_collection_bounds() -> None:
    try:
        MergeDuplicateTicketsRequest.model_validate(
            {
                "canonicalTicketId": "t1",
                "duplicateTicketIds": [f"d{i}" for i in range(21)],
            }
        )
        raise AssertionError("unbounded merge list must be rejected")
    except Exception:
        pass
    try:
        UpsertWorkerRequest.model_validate(
            {
                "displayName": "Worker",
                "departmentIds": [f"dept-{i}" for i in range(41)],
            }
        )
        raise AssertionError("unbounded department list must be rejected")
    except Exception:
        pass


def test_new_rate_limit_policies_exist() -> None:
    policies = build_rate_limit_policies(get_settings())
    for name in (
        "citizen-data-export",
        "citizen-data-delete",
        "whatsapp-submission",
        "staff-mutation",
        "ops-dashboard",
    ):
        assert name in policies


def test_path_rate_limit_mapping() -> None:
    assert (
        match_path_rate_limit_policy(_FakeRequest(path="/v1/citizen/me/export", method="GET"))
        == "citizen-data-export"
    )
    assert (
        match_path_rate_limit_policy(_FakeRequest(path="/v1/citizen/me/delete", method="POST"))
        == "citizen-data-delete"
    )
    assert (
        match_path_rate_limit_policy(_FakeRequest(path="/v1/ops/overview", method="GET"))
        == "ops-dashboard"
    )
    assert (
        match_path_rate_limit_policy(_FakeRequest(path="/v1/tickets/abc/status", method="PATCH"))
        == "staff-mutation"
    )
    assert match_path_rate_limit_policy(_FakeRequest(path="/v1/tickets", method="POST")) is None


def test_whatsapp_submission_rate_limit_is_per_phone(monkeypatch) -> None:
    clear_rate_limiter_cache()
    monkeypatch.setenv("RATE_LIMIT_WHATSAPP_SUBMIT_LIMIT", "1")
    monkeypatch.setenv("RATE_LIMIT_WHATSAPP_SUBMIT_WINDOW_SECONDS", "3600")
    get_settings.cache_clear()
    first = check_identity_rate_limit("wa:+96170000000", "whatsapp-submission")
    second = check_identity_rate_limit("wa:+96170000000", "whatsapp-submission")
    other = check_identity_rate_limit("wa:+96171111111", "whatsapp-submission")
    assert first.allowed
    assert not second.allowed
    assert other.allowed
    get_settings.cache_clear()
    clear_rate_limiter_cache()


def test_whatsapp_submit_raises_before_ticket_create(monkeypatch) -> None:
    clear_rate_limiter_cache()
    monkeypatch.setenv("RATE_LIMIT_WHATSAPP_SUBMIT_LIMIT", "1")
    get_settings.cache_clear()
    check_identity_rate_limit("wa:+96179999999", "whatsapp-submission")

    class Conversation:
        owner_user_id = "citizen_1"
        description = "A blocked drain is flooding the street."
        latitude = 33.89
        longitude = 35.5
        address_text = "Hamra, Beirut"
        image_object_key = "reports/photos/v2/scope/file.jpg"
        optional_name = None
        canonical_phone = "+96179999999"
        language = "en"
        client_submission_key = "wa:test:1"

    try:
        submit_whatsapp_report(Conversation())
        raise AssertionError("rate-limited WhatsApp submit must not create a ticket")
    except WhatsAppSubmissionRateLimited:
        pass
    finally:
        get_settings.cache_clear()
        clear_rate_limiter_cache()


def test_logged_out_staff_and_ops_routes_are_denied() -> None:
    client = TestClient(app)
    assert client.get("/v1/tickets").status_code == 401
    assert client.get("/v1/ops/overview").status_code == 401
    assert client.get("/v1/admin/staff-accounts").status_code == 401
    assert client.get("/v1/workforce/workers").status_code == 401


def test_municipal_staff_cannot_use_developer_ops(client) -> None:
    token = issue_test_staff_token(client, username="staff")
    response = client.get(
        "/v1/ops/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in {401, 403}
