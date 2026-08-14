"""Citizen OTP SNS delivery sandbox and privacy tests."""

from __future__ import annotations

from typing import Any

import pytest
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.services.citizens.otp_delivery import deliver_citizen_otp


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


def test_otp_sandbox_blocks_when_allowlist_empty(monkeypatch, caplog):
    sns = FakeSnsClient()
    monkeypatch.setattr(
        "app.services.citizens.otp_delivery.boto3.client",
        lambda *args, **kwargs: sns,
    )
    settings = _settings(
        notification_adapter="real",
        notification_sandbox=True,
        notification_allowlist_phones=frozenset(),
        app_env="local",
        otp_dev_plaintext_stdout=False,
    )

    deliver_citizen_otp(phone="+9613408680", region="LB", code="123456", settings=settings)

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
        notification_adapter="mock",
        app_env="local",
        otp_dev_plaintext_stdout=False,
    )

    deliver_citizen_otp(phone="+9613408680", region="LB", code="999888", settings=settings)

    assert "999888" not in caplog.text


def test_dev_plaintext_stdout_emits_only_when_switch_enabled(monkeypatch, capsys):
    settings = _settings(
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
        notification_adapter="real",
        notification_sandbox=False,
        app_env="production",
        otp_dev_plaintext_stdout=False,
    )

    with pytest.raises(ClientError):
        deliver_citizen_otp(phone="+9613408680", region="LB", code="445566", settings=settings)
