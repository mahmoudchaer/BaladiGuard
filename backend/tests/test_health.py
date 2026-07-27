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

    def boom(*_args, **_kwargs):
        raise RuntimeError("log boom")

    monkeypatch.setattr(
        "app.services.notifications.service.logger.info",
        boom,
    )

    emit_ticket_notification(
        event="ticket_updated",
        ticket_id="tkt_123",
        status="UNDER_REVIEW",
    )

    assert any("Notification emit failed" in record.message for record in caplog.records)
