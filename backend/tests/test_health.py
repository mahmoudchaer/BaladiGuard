import logging

from app.config import get_settings
from app.services.health import build_health_payload, check_database
from app.services.notifications.service import emit_ticket_notification


def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "baladiguard-api"
    assert body["env"]
    assert body["database"]["backend"] == "memory"
    assert body["database"]["status"] == "ok"


def test_check_database_memory_backend():
    get_settings.cache_clear()
    result = check_database()
    assert result == {"backend": "memory", "status": "ok"}


def test_build_health_payload_includes_database():
    payload = build_health_payload()
    assert payload["status"] in {"ok", "degraded"}
    assert "database" in payload


def test_validation_errors_are_logged(client, caplog):
    caplog.set_level(logging.WARNING)
    response = client.post("/v1/tickets", json={})

    assert response.status_code == 400
    assert any("Request validation failed" in record.message for record in caplog.records)


def test_emit_ticket_notification_logs_without_raising(caplog):
    caplog.set_level(logging.INFO)
    emit_ticket_notification(
        event="ticket_created",
        ticket_id="tkt_123",
        status="SUBMITTED",
        tracking_code="AB12CD",
        ticket_number="BG-2026-0001",
    )

    assert any("Notification mock delivery" in record.message for record in caplog.records)


def test_emit_ticket_notification_never_raises(monkeypatch, caplog):
    caplog.set_level(logging.ERROR)

    class BoomAdapter:
        mode = "mock"

        def deliver(self, *_args, **_kwargs):
            raise RuntimeError("adapter boom")

    monkeypatch.setattr(
        "app.services.notifications.service.build_notification_adapter",
        lambda: BoomAdapter(),
    )

    emit_ticket_notification(
        event="ticket_updated",
        ticket_id="tkt_123",
        status="UNDER_REVIEW",
    )

    assert any("Notification emit failed" in record.message for record in caplog.records)


def test_check_database_memory_failure_returns_error(monkeypatch):
    class BrokenStore:
        def list(self):
            raise RuntimeError("store boom")

    monkeypatch.setattr("app.services.health.get_ticket_store", lambda: BrokenStore())
    result = check_database()
    assert result["backend"] == "memory"
    assert result["status"] == "error"
    assert result["detail"] == "RuntimeError"
    assert build_health_payload()["status"] == "degraded"


def test_unhandled_error_includes_request_id_header():
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()

    @app.get("/__boom")
    def boom():
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as failing_client:
        response = failing_client.get("/__boom")

    assert response.status_code == 500
    assert "X-Request-Id" in response.headers
    assert response.json()["error"]["requestId"] == response.headers["X-Request-Id"]
