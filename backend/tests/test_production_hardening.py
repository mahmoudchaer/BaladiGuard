"""Production security / abuse hardening coverage (issue #316)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.body_limits import (
    json_nesting_too_deep,
    json_text_nesting_too_deep,
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
from app.schemas.ticket import SubmitTicketResponse
from app.schemas.ticket_merge import MergeDuplicateTicketsRequest
from app.schemas.workforce import UpsertWorkerRequest
from app.services.complaints.ticket_service import ticket_service
from app.services.complaints.ticket_submission_idempotency import (
    composite_submission_key,
    get_ticket_submission_idempotency_store,
    normalize_client_submission_key,
    reset_ticket_submission_idempotency_store,
)
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


def test_http_rejects_over_nested_json_body() -> None:
    nested: object = {"ok": True}
    for _ in range(get_settings().max_json_nesting_depth + 2):
        nested = {"child": nested}
    client = TestClient(app)
    response = client.post("/v1/locations/validate", json=nested)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_NESTED"


def _decoder_limit_nested_json(*, layers: int = 20_000) -> bytes:
    return b'{"child":' * layers + b"1" + b"}" * layers


def test_json_text_scan_rejects_before_decoder_recursion() -> None:
    raw = _decoder_limit_nested_json()
    assert json_text_nesting_too_deep(raw, max_depth=get_settings().max_json_nesting_depth)
    assert not json_text_nesting_too_deep(b'{"ok":{"child":1}}', max_depth=20)
    with pytest.raises(RecursionError):
        json.loads(raw)


def test_http_rejects_json_deeper_than_cpython_decoder_limit() -> None:
    raw = _decoder_limit_nested_json()
    client = TestClient(app)
    response = client.post(
        "/v1/locations/validate",
        content=raw,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_NESTED"


def test_http_maps_json_decoder_recursion_error_to_payload_too_nested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decode = json.loads

    def boom(_raw: object) -> object:
        raise RecursionError("simulated decoder overflow")

    monkeypatch.setattr("app.core.body_limits.json.loads", boom)
    client = TestClient(app)
    response = client.post(
        "/v1/locations/validate",
        content=b'{"ok":true}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert decode(response.content)["error"]["code"] == "PAYLOAD_TOO_NESTED"


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


def test_whatsapp_retry_reuses_idempotent_ticket_under_tight_limit(monkeypatch) -> None:
    clear_rate_limiter_cache()
    reset_ticket_submission_idempotency_store()
    monkeypatch.setenv("RATE_LIMIT_WHATSAPP_SUBMIT_LIMIT", "1")
    monkeypatch.setenv("RATE_LIMIT_WHATSAPP_SUBMIT_WINDOW_SECONDS", "3600")
    get_settings.cache_clear()

    created = SubmitTicketResponse(
        ticketId="tkt_wa_retry",
        ticketNumber="BG-2026-8801",
        trackingCode="WARETRY",
        status="SUBMITTED",
        message="accepted",
        createdAt="2026-08-22T00:00:00Z",
    )
    calls = {"n": 0}

    def fake_submit(*_args, **_kwargs):
        calls["n"] += 1
        key = normalize_client_submission_key("wa:biz:sender:retry01")
        assert key is not None
        store = get_ticket_submission_idempotency_store()
        composite = composite_submission_key(owner_user_id="citizen_retry", client_key=key)
        store.complete(composite, created)
        return created

    monkeypatch.setattr(ticket_service, "submit_ticket", fake_submit)

    class Conversation:
        owner_user_id = "citizen_retry"
        description = "A blocked drain is flooding the street."
        latitude = 33.89
        longitude = 35.5
        address_text = "Hamra, Beirut"
        image_object_key = "reports/photos/v2/scope/file.jpg"
        optional_name = None
        canonical_phone = "+96170002222"
        language = "en"
        client_submission_key = "wa:biz:sender:retry01"

    first = submit_whatsapp_report(Conversation())
    second = submit_whatsapp_report(Conversation())
    assert first.ticket_id == "tkt_wa_retry"
    assert second.ticket_id == "tkt_wa_retry"
    assert calls["n"] == 2

    class FreshConversation(Conversation):
        client_submission_key = "wa:biz:sender:retry02"

    try:
        submit_whatsapp_report(FreshConversation())
        raise AssertionError("a new WhatsApp submission key must still consume the phone quota")
    except WhatsAppSubmissionRateLimited:
        pass
    finally:
        get_settings.cache_clear()
        clear_rate_limiter_cache()
        reset_ticket_submission_idempotency_store()


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
