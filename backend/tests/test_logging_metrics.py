"""Tests for structured logging, redaction, and metric helpers (issue #185)."""

from __future__ import annotations

import json
import logging

from app.core.logging import JsonLogFormatter, configure_logging, redact_mapping
from app.core.metrics import emit_metric, normalize_path_group
from app.core.request_context import get_request_id, reset_request_id, set_request_id


def test_redact_mapping_masks_sensitive_keys():
    redacted = redact_mapping(
        {
            "username": "staff",
            "password": "super-secret",
            "reset_code": "123456",
            "nested": {"access_token": "abc", "ok": 1},
        }
    )
    assert redacted["username"] == "staff"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["reset_code"] == "[REDACTED]"
    assert redacted["nested"]["access_token"] == "[REDACTED]"
    assert redacted["nested"]["ok"] == 1


def test_json_log_formatter_includes_request_id_version_and_redacts_extras(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "1.2.3-test")
    monkeypatch.setenv("APP_ENV", "staging")
    token = set_request_id("req_test123")
    try:
        formatter = JsonLogFormatter()
        record = logging.LogRecord(
            name="app.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        record.password = "nope"
        record.ticket_id = "tkt_abc"
        payload = json.loads(formatter.format(record))
    finally:
        reset_request_id(token)

    assert payload["message"] == "hello"
    assert payload["request_id"] == "req_test123"
    assert payload["version"] == "1.2.3-test"
    assert payload["env"] == "staging"
    assert payload["extra"]["password"] == "[REDACTED]"
    assert payload["extra"]["ticket_id"] == "tkt_abc"


def test_normalize_path_group_collapses_ids():
    assert (
        normalize_path_group("/v1/tickets/tkt_deadbeef0123456789abcdef/status")
        == "/v1/tickets/:ticketId/status"
    )
    assert normalize_path_group("/v1/tickets/BG-2026-0042") == "/v1/tickets/:ticketNumber"


def test_emit_metric_writes_filterable_log_line(caplog, monkeypatch):
    monkeypatch.setenv("METRICS_EMF", "false")
    monkeypatch.setenv("APP_ENV", "local")
    caplog.set_level(logging.INFO)
    token = set_request_id("req_metric1")
    try:
        emit_metric("Http5xx", dimensions={"status_class": "5xx", "path": "/v1/tickets"})
    finally:
        reset_request_id(token)

    assert any(
        "metric_event name=Http5xx" in record.message and "request_id=req_metric1" in record.message
        for record in caplog.records
    )
    assert get_request_id() is None


def test_configure_logging_json_mode(monkeypatch):
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    root = logging.getLogger()
    root.handlers.clear()
    configure_logging()
    assert root.handlers
    assert isinstance(root.handlers[0].formatter, JsonLogFormatter)
    root.handlers.clear()
