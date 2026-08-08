"""Citizen OTP SNS delivery sandbox tests."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.services.citizens.otp_delivery import deliver_citizen_otp


class FakeSnsClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def publish(self, **kwargs):
        self.calls.append(kwargs)
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
    )

    deliver_citizen_otp(phone="+9613408680", region="LB", code="123456", settings=settings)

    assert sns.calls == []
    assert "OTP SMS blocked by notification sandbox allowlist" in caplog.text
    assert "LOCAL OTP FALLBACK" in caplog.text


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
    )

    deliver_citizen_otp(phone="+9613408680", region="LB", code="654321", settings=settings)

    assert len(sns.calls) == 1
    assert sns.calls[0]["PhoneNumber"] == "+9613408680"
    assert "Citizen OTP SMS published" in caplog.text
