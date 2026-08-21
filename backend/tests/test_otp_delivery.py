"""Citizen OTP SNS / WhatsApp delivery tests (issue #297)."""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any
from urllib.error import HTTPError

import pytest
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.services.citizens.otp_delivery import (
    OtpDeliveryError,
    build_whatsapp_otp_payload,
    deliver_citizen_otp,
    public_otp_delivery_channel,
    resolve_citizen_otp_delivery_channel,
    session_otp_text_body,
)


class FakeSnsClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self._fail = fail

    def publish(self, **kwargs):
        self.calls.append(kwargs)
        if self._fail:
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "boom"}},
                "Publish",
            )
        return {"MessageId": "sns-otp-1"}


def _settings(**overrides: object) -> Settings:
    get_settings.cache_clear()
    settings = Settings()
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def test_resolve_channel_explicit_and_legacy_defaults():
    assert (
        resolve_citizen_otp_delivery_channel(
            _settings(citizen_otp_delivery_channel="whatsapp", notification_adapter="mock")
        )
        == "whatsapp"
    )
    assert (
        resolve_citizen_otp_delivery_channel(
            _settings(
                citizen_otp_delivery_channel=None, notification_adapter="mock", app_env="local"
            )
        )
        == "mock"
    )
    assert (
        resolve_citizen_otp_delivery_channel(
            _settings(
                citizen_otp_delivery_channel=None, notification_adapter="real", app_env="production"
            )
        )
        == "sns"
    )
    assert public_otp_delivery_channel("sns") == "sms"
    assert public_otp_delivery_channel("whatsapp") == "whatsapp"


def test_otp_sandbox_blocks_when_allowlist_empty(monkeypatch, caplog):
    sns = FakeSnsClient()
    monkeypatch.setattr(
        "app.services.citizens.otp_delivery.boto3.client",
        lambda *args, **kwargs: sns,
    )
    settings = _settings(
        citizen_otp_delivery_channel="sns",
        notification_adapter="real",
        notification_sandbox=True,
        notification_allowlist_phones=frozenset(),
        app_env="local",
        otp_dev_plaintext_stdout=False,
    )

    assert (
        deliver_citizen_otp(phone="+9613408680", region="LB", code="123456", settings=settings)
        == "sms"
    )

    assert sns.calls == []
    assert "OTP SMS blocked by notification sandbox allowlist" in caplog.text
    assert "123456" not in caplog.text


def test_otp_sandbox_allows_allowlisted_phone(monkeypatch, caplog):
    sns = FakeSnsClient()
    monkeypatch.setattr(
        "app.services.citizens.otp_delivery.boto3.client",
        lambda *args, **kwargs: sns,
    )
    settings = _settings(
        citizen_otp_delivery_channel="sns",
        notification_adapter="real",
        notification_sandbox=True,
        notification_allowlist_phones=frozenset({"+9613408680"}),
        app_env="local",
        otp_dev_plaintext_stdout=False,
    )

    deliver_citizen_otp(phone="+9613408680", region="LB", code="654321", settings=settings)

    assert len(sns.calls) == 1
    assert sns.calls[0]["PhoneNumber"] == "+9613408680"
    assert "Citizen OTP SMS published" in caplog.text
    assert "654321" not in caplog.text


def test_mock_adapter_does_not_log_otp_code(caplog):
    settings = _settings(
        citizen_otp_delivery_channel="mock",
        notification_adapter="mock",
        app_env="local",
        otp_dev_plaintext_stdout=False,
    )

    assert (
        deliver_citizen_otp(phone="+9613408680", region="LB", code="999888", settings=settings)
        == "dev"
    )
    assert "999888" not in caplog.text


def test_dev_plaintext_stdout_emits_only_when_switch_enabled(monkeypatch, capsys):
    settings = _settings(
        citizen_otp_delivery_channel="mock",
        notification_adapter="mock",
        app_env="local",
        otp_dev_plaintext_stdout=True,
    )

    deliver_citizen_otp(phone="+9613408680", region="LB", code="112233", settings=settings)

    captured = capsys.readouterr()
    assert "OTP_DEV_PLAINTEXT" in captured.out
    assert "112233" in captured.out


def test_dev_plaintext_stdout_emits_after_successful_sns_publish(monkeypatch, capsys, caplog):
    sns = FakeSnsClient()
    monkeypatch.setattr(
        "app.services.citizens.otp_delivery.boto3.client",
        lambda *args, **kwargs: sns,
    )
    settings = _settings(
        citizen_otp_delivery_channel="sns",
        notification_adapter="real",
        notification_sandbox=False,
        app_env="local",
        otp_dev_plaintext_stdout=True,
    )

    deliver_citizen_otp(phone="+9613408680", region="LB", code="778899", settings=settings)

    captured = capsys.readouterr()
    assert len(sns.calls) == 1
    assert "reason=sns_published" in captured.out
    assert "778899" in captured.out
    assert "778899" not in caplog.text


def test_sns_publish_failure_raises_outside_local(monkeypatch):
    sns = FakeSnsClient(fail=True)
    monkeypatch.setattr(
        "app.services.citizens.otp_delivery.boto3.client",
        lambda *args, **kwargs: sns,
    )
    settings = _settings(
        citizen_otp_delivery_channel="sns",
        notification_adapter="real",
        notification_sandbox=False,
        app_env="production",
        otp_dev_plaintext_stdout=False,
    )

    with pytest.raises(OtpDeliveryError):
        deliver_citizen_otp(phone="+9613408680", region="LB", code="445566", settings=settings)


def test_whatsapp_builds_template_request_without_logging_code(monkeypatch, caplog):
    captured: dict[str, Any] = {}

    class FakeResponse:
        def read(self, _n: int = -1) -> bytes:
            return b'{"messages":[{"id":"wamid.1"}]}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=0):  # noqa: ARG001
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["auth"] = request.get_header("Authorization")
        return FakeResponse()

    monkeypatch.setattr("app.services.citizens.otp_delivery.urlopen", fake_urlopen)
    settings = _settings(
        citizen_otp_delivery_channel="whatsapp",
        citizen_otp_whatsapp_message_mode="template",
        citizen_otp_whatsapp_access_token="meta-token",
        citizen_otp_whatsapp_phone_number_id="pnid_1",
        citizen_otp_whatsapp_template_name="baladiguard_auth",
        citizen_otp_whatsapp_template_language="en",
        citizen_otp_whatsapp_template_button_index=0,
        notification_sandbox=False,
        app_env="production",
        otp_dev_plaintext_stdout=False,
    )

    assert (
        deliver_citizen_otp(phone="+9613408680", region="LB", code="121212", settings=settings)
        == "whatsapp"
    )
    assert captured["body"]["to"] == "9613408680"
    assert captured["body"]["type"] == "template"
    assert captured["body"]["template"]["name"] == "baladiguard_auth"
    params = captured["body"]["template"]["components"][0]["parameters"]
    assert params[0]["text"] == "121212"
    assert "121212" not in caplog.text
    assert "meta-token" not in caplog.text


def test_whatsapp_http_error_raises_in_production(monkeypatch):
    def fake_urlopen(request, timeout=0):  # noqa: ARG001
        raise HTTPError(request.full_url, 401, "Unauthorized", hdrs=None, fp=None)  # type: ignore[arg-type]

    monkeypatch.setattr("app.services.citizens.otp_delivery.urlopen", fake_urlopen)
    settings = _settings(
        citizen_otp_delivery_channel="whatsapp",
        citizen_otp_whatsapp_message_mode="template",
        citizen_otp_whatsapp_access_token="meta-token",
        citizen_otp_whatsapp_phone_number_id="pnid_1",
        citizen_otp_whatsapp_template_name="baladiguard_auth",
        notification_sandbox=False,
        app_env="production",
        otp_dev_plaintext_stdout=False,
    )

    with pytest.raises(OtpDeliveryError) as exc_info:
        deliver_citizen_otp(phone="+9613408680", region="LB", code="343434", settings=settings)
    assert exc_info.value.category == "whatsapp_auth"


def test_whatsapp_and_sns_never_both_called(monkeypatch):
    sns = FakeSnsClient()
    monkeypatch.setattr(
        "app.services.citizens.otp_delivery.boto3.client",
        lambda *args, **kwargs: sns,
    )
    called = {"wa": 0}

    class FakeResponse:
        def read(self, _n: int = -1) -> bytes:
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=0):  # noqa: ARG001
        called["wa"] += 1
        return FakeResponse()

    monkeypatch.setattr("app.services.citizens.otp_delivery.urlopen", fake_urlopen)
    settings = _settings(
        citizen_otp_delivery_channel="whatsapp",
        citizen_otp_whatsapp_message_mode="template",
        citizen_otp_whatsapp_access_token="meta-token",
        citizen_otp_whatsapp_phone_number_id="pnid_1",
        citizen_otp_whatsapp_template_name="baladiguard_auth",
        notification_sandbox=False,
        app_env="production",
        otp_dev_plaintext_stdout=False,
    )
    deliver_citizen_otp(phone="+9613408680", region="LB", code="565656", settings=settings)
    assert called["wa"] == 1
    assert sns.calls == []


def test_whatsapp_session_text_payload_for_allowlisted_sandbox(monkeypatch, caplog):
    captured: dict[str, Any] = {}

    class FakeResponse:
        def read(self, _n: int = -1) -> bytes:
            return b'{"messages":[{"id":"wamid.session"}]}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=0):  # noqa: ARG001
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("app.services.citizens.otp_delivery.urlopen", fake_urlopen)
    settings = _settings(
        citizen_otp_delivery_channel="whatsapp",
        citizen_otp_whatsapp_message_mode="session_text",
        citizen_otp_whatsapp_access_token="meta-token",
        citizen_otp_whatsapp_phone_number_id="pnid_1",
        citizen_otp_whatsapp_template_name=None,
        notification_sandbox=True,
        notification_allowlist_phones=frozenset({"+9613408680"}),
        app_env="local",
        otp_dev_plaintext_stdout=False,
    )

    assert (
        deliver_citizen_otp(phone="+9613408680", region="LB", code="121314", settings=settings)
        == "whatsapp"
    )
    assert captured["body"]["type"] == "text"
    assert captured["body"]["to"] == "9613408680"
    assert captured["body"]["text"]["body"] == session_otp_text_body("121314")
    assert "template" not in captured["body"]
    assert "121314" not in caplog.text


def test_whatsapp_session_text_forbidden_without_sandbox():
    settings = _settings(
        citizen_otp_delivery_channel="whatsapp",
        citizen_otp_whatsapp_message_mode="session_text",
        citizen_otp_whatsapp_access_token="meta-token",
        citizen_otp_whatsapp_phone_number_id="pnid_1",
        notification_sandbox=False,
        app_env="local",
        otp_dev_plaintext_stdout=False,
    )
    with pytest.raises(OtpDeliveryError) as exc_info:
        deliver_citizen_otp(phone="+9613408680", region="LB", code="151617", settings=settings)
    assert exc_info.value.category == "whatsapp_session_text_forbidden"


def test_whatsapp_session_window_closed_is_classified(monkeypatch):
    def fake_urlopen(request, timeout=0):  # noqa: ARG001
        payload = json.dumps({"error": {"code": 131047, "message": "re-engagement"}}).encode()
        raise HTTPError(
            request.full_url,
            400,
            "Bad Request",
            hdrs=None,
            fp=BytesIO(payload),  # type: ignore[arg-type]
        )

    monkeypatch.setattr("app.services.citizens.otp_delivery.urlopen", fake_urlopen)
    settings = _settings(
        citizen_otp_delivery_channel="whatsapp",
        citizen_otp_whatsapp_message_mode="session_text",
        citizen_otp_whatsapp_access_token="meta-token",
        citizen_otp_whatsapp_phone_number_id="pnid_1",
        notification_sandbox=True,
        notification_allowlist_phones=frozenset({"+9613408680"}),
        app_env="local",
        otp_dev_plaintext_stdout=False,
    )
    with pytest.raises(OtpDeliveryError) as exc_info:
        deliver_citizen_otp(phone="+9613408680", region="LB", code="181920", settings=settings)
    assert exc_info.value.category == "whatsapp_session_window_closed"


def test_build_template_payload_unchanged_by_session_helper():
    settings = _settings(
        citizen_otp_whatsapp_message_mode="template",
        citizen_otp_whatsapp_template_name="baladiguard_auth",
        citizen_otp_whatsapp_template_language="en",
        citizen_otp_whatsapp_template_button_index=None,
    )
    payload = build_whatsapp_otp_payload(
        canonical_phone="+9613408680", code="212223", settings=settings
    )
    assert payload["type"] == "template"
    assert payload["template"]["name"] == "baladiguard_auth"
