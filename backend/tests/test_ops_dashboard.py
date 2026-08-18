"""Developer-operator dashboard API coverage (issue #320)."""

from __future__ import annotations

import time

from app.core.metrics import emit_metric
from app.database.memory_ai_job import ai_job_store
from app.database.memory_ops import ops_audit_store
from app.database.store_factory import get_ticket_store
from tests.conftest import issue_test_staff_token


def _headers(client, username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username=username)}"}


def _assert_no_secrets(body: object) -> None:
    rendered = str(body).lower()
    for forbidden in (
        "password",
        "secret_key",
        "accesskey",
        "secretaccess",
        "otp",
        "presigned",
        "authorization: bearer",
        "staff-demo-password",
    ):
        assert forbidden not in rendered


def test_ops_overview_is_denied_to_guests_staff_and_administrators(anonymous_client):
    response = anonymous_client.get("/v1/ops/overview")
    assert response.status_code == 401
    admin = anonymous_client.get("/v1/ops/overview", headers=_headers(anonymous_client, "admin"))
    assert admin.status_code == 403
    staff = anonymous_client.get("/v1/ops/overview", headers=_headers(anonymous_client, "staff"))
    assert staff.status_code == 403


def test_citizen_token_cannot_open_ops(anonymous_client, contribution_ready_citizen_headers):
    response = anonymous_client.get(
        "/v1/ops/overview",
        headers=contribution_ready_citizen_headers,
    )
    assert response.status_code in {401, 403}


def test_operator_can_read_overview_metrics_alerts_workers_and_runbooks(anonymous_client):
    headers = _headers(anonymous_client, "operator")
    overview = anonymous_client.get("/v1/ops/overview", headers=headers)
    assert overview.status_code == 200, overview.text
    body = overview.json()
    _assert_no_secrets(body)
    assert body["health"]["env"] == "test"
    assert body["health"]["version"]
    assert body["health"]["ready"] is True
    assert body["health"]["database"] in {"ok", "unknown"}
    assert body["telemetrySource"] in {"application", "cloudwatch", "mixed"}
    assert body["municipalityManagement"]["available"] is False
    assert {item["kind"] for item in body["workers"]} >= {
        "ai",
        "redaction",
        "notifications",
        "whatsapp",
        "moderation",
    }
    assert any(item["kind"] == "whatsapp" and item["deployed"] is False for item in body["workers"])

    metrics = anonymous_client.get("/v1/ops/metrics?range=1h", headers=headers)
    assert metrics.status_code == 200
    names = {item["name"] for item in metrics.json()["series"]}
    assert "HttpRequests" in names
    assert "ReportsSubmitted" in names

    alerts = anonymous_client.get("/v1/ops/alerts", headers=headers)
    assert alerts.status_code == 200
    assert "items" in alerts.json()

    workers = anonymous_client.get("/v1/ops/workers", headers=headers)
    assert workers.status_code == 200
    assert "queues" in workers.json()

    runbooks = anonymous_client.get("/v1/ops/runbooks", headers=headers)
    assert runbooks.status_code == 200
    assert any(item["alarmName"] == "BaladiGuard-Sustained5xx" for item in runbooks.json()["items"])


def test_ops_filters_reject_unsafe_input(anonymous_client):
    headers = _headers(anonymous_client, "operator")
    bad_range = anonymous_client.get("/v1/ops/overview?range=drop-table", headers=headers)
    assert bad_range.status_code == 400
    bad_service = anonymous_client.get("/v1/ops/overview?service=<script>", headers=headers)
    assert bad_service.status_code == 400
    bad_muni = anonymous_client.get("/v1/ops/product?municipalityId=not-a-uuid", headers=headers)
    assert bad_muni.status_code == 400


def test_ops_empty_states_are_safe_arrays(anonymous_client):
    headers = _headers(anonymous_client, "operator")
    errors = anonymous_client.get("/v1/ops/errors", headers=headers)
    assert errors.status_code == 200
    assert errors.json()["items"] == []
    workers = anonymous_client.get("/v1/ops/workers?jobType=moderation", headers=headers)
    assert workers.json()["jobs"] == []
    assert workers.json()["queues"][0]["deployed"] is False


def test_operator_can_acknowledge_alert_with_audit(anonymous_client):
    headers = _headers(anonymous_client, "operator")
    response = anonymous_client.post(
        "/v1/ops/alerts/BaladiGuard-Sustained5xx/ack",
        headers=headers,
        json={"note": "Investigating latency; contact otp=123456 ignored"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ackStatus"] == "acknowledged"
    assert body["ackBy"] == "operator"
    assert "123456" not in str(body)
    audits = ops_audit_store.list_recent()
    assert any(item.action_type == "ALERT_ACKNOWLEDGED" for item in audits)


def test_operator_cannot_ack_arbitrary_alarm_names(anonymous_client):
    headers = _headers(anonymous_client, "operator")
    response = anonymous_client.post(
        "/v1/ops/alerts/not-an-alarm/ack",
        headers=headers,
        json={},
    )
    assert response.status_code == 400


def test_cloudwatch_failure_falls_back_to_application_telemetry(anonymous_client, monkeypatch):
    from app.services.observability import cloudwatch

    def _boom(**_kwargs):
        raise cloudwatch.CloudWatchUnavailable("access denied")

    monkeypatch.setattr(cloudwatch, "fetch_metric_data", _boom)
    monkeypatch.setattr(cloudwatch, "describe_ops_alarms", _boom)
    headers = _headers(anonymous_client, "operator")
    emit_metric("Http5xx", value=3)
    response = anonymous_client.get("/v1/ops/overview", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["telemetrySource"] == "application"
    assert body["telemetryWarning"]


def test_operator_can_replay_dead_lettered_ai_job(anonymous_client):
    headers = _headers(anonymous_client, "operator")
    now = int(time.time())
    job = ai_job_store.enqueue("tkt_deadletter", now)
    claimed = ai_job_store.claim_next(now=now, claim_ttl_seconds=30)
    assert claimed is not None
    assert ai_job_store.dead_letter(
        claimed.job_id, claimed.claim_token or "", now=now, reason="Bedrock timeout"
    )
    response = anonymous_client.post(
        f"/v1/ops/workers/jobs/{job.job_id}/replay",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["replayed"] is True
    replayed = ai_job_store.get(job.job_id)
    assert replayed is not None
    assert replayed.status == "queued"


def test_replay_rejects_unsafe_job_ids(anonymous_client):
    headers = _headers(anonymous_client, "operator")
    response = anonymous_client.post(
        "/v1/ops/workers/jobs/../secrets/replay",
        headers=headers,
    )
    assert response.status_code in {400, 404, 405, 422}


def test_http_5xx_is_recorded_in_error_catalog(anonymous_client):
    headers = _headers(anonymous_client, "operator")
    emit_metric("HttpRequests")
    from app.services.observability.snapshot import record_http_error

    record_http_error(path_group="/v1/tickets", status_code=500, request_id="req_abc123")
    errors = anonymous_client.get("/v1/ops/errors", headers=headers)
    assert errors.status_code == 200
    items = errors.json()["items"]
    assert items
    assert items[0]["lastRequestId"] == "req_abc123"
    assert "description" not in items[0]


def test_product_metrics_use_aggregates_not_ticket_text(anonymous_client):
    headers = _headers(anonymous_client, "operator")
    emit_metric("ReportsSubmitted")
    response = anonymous_client.get("/v1/ops/product", headers=headers)
    assert response.status_code == 200
    body = response.json()
    _assert_no_secrets(body)
    assert "reportsSubmitted" in body
    rendered = str(body).lower()
    assert "pothole" not in rendered
    tickets = get_ticket_store().list()
    for ticket in tickets:
        assert ticket.description not in rendered


def test_municipal_admin_cannot_create_developer_operator(anonymous_client):
    headers = _headers(anonymous_client, "admin")
    response = anonymous_client.post(
        "/v1/admin/staff-accounts",
        headers=headers,
        json={
            "username": "rogue-ops",
            "name": "Rogue",
            "email": "rogue@example.com",
            "password": "password1234",
            "role": "developer_operator",
        },
    )
    assert response.status_code in {400, 422}
    listed = anonymous_client.get("/v1/admin/staff-accounts", headers=headers)
    assert listed.status_code == 200
    assert all(item["role"] != "developer_operator" for item in listed.json())


def test_operator_cannot_browse_tickets(anonymous_client):
    headers = _headers(anonymous_client, "operator")
    response = anonymous_client.get("/v1/tickets", headers=headers)
    assert response.status_code == 403
