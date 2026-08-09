"""Tests for structured logging, redaction, and metric helpers (issue #185)."""

from __future__ import annotations

import json
import logging
import sys

from app.core.logging import (
    JsonLogFormatter,
    configure_logging,
    redact_mapping,
    redact_text,
)
from app.core.metrics import build_emf_record, emit_metric, normalize_path_group
from app.core.readiness_probe import publish_ready_probe_once
from app.core.request_context import get_request_id, reset_request_id, set_request_id


def test_redact_mapping_masks_sensitive_keys_and_nested_sequences():
    redacted = redact_mapping(
        {
            "username": "staff",
            "password": "super-secret",
            "reset_code": "123456",
            "nested": {"access_token": "abc", "ok": 1},
            "items": [{"token": "xyz"}, ("password", "hunter2"), "otp=999999"],
        }
    )
    assert redacted["username"] == "staff"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["reset_code"] == "[REDACTED]"
    assert redacted["nested"]["access_token"] == "[REDACTED]"
    assert redacted["nested"]["ok"] == 1
    assert redacted["items"][0]["token"] == "[REDACTED]"
    assert redacted["items"][1] == ("password", "[REDACTED]")
    assert redacted["items"][2] == "otp=[REDACTED]"


def test_redact_text_masks_quoted_spaced_and_auth_credentials():
    assert "hunter2" not in redact_text("login failed: password=hunter2")
    assert "password=[REDACTED]" in redact_text("login failed: password=hunter2")

    quoted = redact_text('password="my secret value"')
    assert "my secret value" not in quoted
    assert quoted == "password=[REDACTED]" or "password=[REDACTED]" in quoted

    spaced = redact_text("api_key = secret with spaces")
    assert "secret with spaces" not in spaced
    assert "api_key=[REDACTED]" in spaced.replace(" ", "") or "api_key=[REDACTED]" in spaced

    basic = redact_text("Authorization: Basic dXNlcjpwYXNz")
    assert "dXNlcjpwYXNz" not in basic
    assert "Basic [REDACTED]" in basic

    bearer = redact_text("Authorization: Bearer secret-value")
    assert "secret-value" not in bearer
    assert "Bearer [REDACTED]" in bearer

    digest = redact_text(
        'Authorization: Digest username="Mufasa", realm="test", nonce="abc", response="deadbeef"'
    )
    assert "Mufasa" not in digest
    assert "deadbeef" not in digest
    assert "realm" not in digest
    assert "Digest [REDACTED]" in digest


def test_json_log_formatter_redacts_message_args_and_exception(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "1.2.3-test")
    monkeypatch.setenv("APP_ENV", "staging")
    token = set_request_id("req_test123")
    try:
        formatter = JsonLogFormatter()
        record = logging.LogRecord(
            name="app.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="login failed: password=%s",
            args=("hunter2",),
            exc_info=None,
        )
        record.password = "nope"
        record.ticket_id = "tkt_abc"
        try:
            raise RuntimeError('provider rejected token="abc 123"')
        except RuntimeError:
            record.exc_info = sys.exc_info()
        payload = json.loads(formatter.format(record))
    finally:
        reset_request_id(token)

    assert "hunter2" not in payload["message"]
    assert "password=[REDACTED]" in payload["message"]
    assert payload["request_id"] == "req_test123"
    assert payload["version"] == "1.2.3-test"
    assert payload["env"] == "staging"
    assert payload["extra"]["password"] == "[REDACTED]"
    assert payload["extra"]["ticket_id"] == "tkt_abc"
    assert payload["exception"]["type"] == "RuntimeError"
    assert "abc 123" not in payload["exception"]["message"]
    assert "token=[REDACTED]" in payload["exception"]["message"]
    assert "abc 123" not in payload["exception_traceback"]


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


def test_emf_record_uses_stable_env_dimension_only():
    emf = build_emf_record("Http5xx", value=1.0, unit="Count", env="production")
    assert emf["_aws"]["CloudWatchMetrics"][0]["Dimensions"] == [["env"]]
    assert emf["env"] == "production"
    assert set(emf.keys()) == {"_aws", "Http5xx", "env"}


def test_configure_logging_json_mode(monkeypatch):
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    root = logging.getLogger()
    root.handlers.clear()
    configure_logging()
    assert root.handlers
    assert isinstance(root.handlers[0].formatter, JsonLogFormatter)
    root.handlers.clear()


def test_publish_ready_probe_once_uses_injected_builder():
    calls: list[int] = []

    def builder():
        calls.append(1)
        return {"status": "ready"}, True

    assert publish_ready_probe_once(builder) is True
    assert calls == [1]


def test_build_readiness_emits_ready_probe_metric(caplog, monkeypatch):
    from app.services.health import build_readiness_payload

    monkeypatch.setenv("METRICS_EMF", "false")
    caplog.set_level(logging.INFO)
    payload, ok = build_readiness_payload()
    assert ok is True
    assert payload["status"] == "ready"
    assert any("ReadyProbeSuccess" in r.message for r in caplog.records)
