"""Real SES/SNS notification adapter tests (issue #183)."""

from __future__ import annotations

import logging
from typing import Any

import pytest
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.memory_notification_delivery import notification_delivery_store
from app.services.notifications.adapters import (
    NotificationDeliveryError,
    NotificationRecipient,
    UnconfiguredRealNotificationAdapter,
    build_notification_adapter,
)
from app.services.notifications.aws_adapter import (
    AwsSesSnsNotificationAdapter,
    DestinationThrottle,
    is_valid_e164_phone,
    is_valid_email,
)
from app.services.notifications.service import emit_ticket_notification
from app.services.notifications.templates import render_ticket_created


class FakeSesClient:
    def __init__(self, *, fail_code: str | None = None) -> None:
        self.fail_code = fail_code
        self.calls: list[dict[str, Any]] = []

    def send_email(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_code:
            raise ClientError(
                {"Error": {"Code": self.fail_code, "Message": "denied"}},
                "SendEmail",
            )
        return {"MessageId": "ses-msg-1"}


class FakeSnsClient:
    def __init__(self, *, fail_code: str | None = None) -> None:
        self.fail_code = fail_code
        self.calls: list[dict[str, Any]] = []

    def publish(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_code:
            raise ClientError(
                {"Error": {"Code": self.fail_code, "Message": "denied"}},
                "Publish",
            )
        return {"MessageId": "sns-msg-1"}


def _settings(**overrides: object) -> Settings:
    get_settings.cache_clear()
    settings = Settings()
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def test_is_valid_email_and_phone():
    assert is_valid_email("citizen@example.com")
    assert not is_valid_email("not-an-email")
    assert is_valid_e164_phone("+96170123456")
    assert not is_valid_e164_phone("70123456")


def test_build_real_adapter_unconfigured_without_channels(monkeypatch):
    monkeypatch.setenv("SES_FROM_EMAIL", "")
    monkeypatch.setenv("NOTIFICATION_ALLOW_SMS_ONLY_REAL", "false")
    get_settings.cache_clear()
    adapter = build_notification_adapter("real")
    assert isinstance(adapter, UnconfiguredRealNotificationAdapter)
    get_settings.cache_clear()


def test_build_real_adapter_uses_aws_when_ses_configured(monkeypatch):
    monkeypatch.setenv("SES_FROM_EMAIL", "noreply@example.com")
    get_settings.cache_clear()
    adapter = build_notification_adapter("real")
    assert isinstance(adapter, AwsSesSnsNotificationAdapter)
    get_settings.cache_clear()


def test_aws_adapter_sends_email_success():
    ses = FakeSesClient()
    settings = _settings(
        ses_from_email="noreply@example.com",
        notification_sandbox=False,
    )
    adapter = AwsSesSnsNotificationAdapter(
        settings=settings, ses_client=ses, sns_client=FakeSnsClient()
    )
    message = render_ticket_created(ticket_id="tkt_1", ticket_number="BG-1", tracking_code="AB23CD")
    results = adapter.deliver(
        message,
        NotificationRecipient(email="user@example.com", preferred_channel="EMAIL"),
    )
    assert len(results) == 1
    assert results[0].status == "SUCCEEDED"
    assert results[0].provider_message_id == "ses-msg-1"
    assert ses.calls[0]["Source"] == "noreply@example.com"
    assert ses.calls[0]["Destination"]["ToAddresses"] == ["user@example.com"]
    # Body is citizen template only — no staff fields.
    body = ses.calls[0]["Message"]["Body"]["Text"]["Data"]
    assert "staff" not in body.lower()
    assert "password" not in body.lower()


def test_aws_adapter_sends_sms_success():
    sns = FakeSnsClient()
    settings = _settings(notification_sandbox=False, sns_sms_sender_id="Baladi")
    adapter = AwsSesSnsNotificationAdapter(
        settings=settings, ses_client=FakeSesClient(), sns_client=sns
    )
    message = render_ticket_created(ticket_id="tkt_2")
    results = adapter.deliver(
        message,
        NotificationRecipient(phone="+96170123456", preferred_channel="SMS"),
    )
    assert results[0].status == "SUCCEEDED"
    assert sns.calls[0]["PhoneNumber"] == "+96170123456"
    assert "Subject" not in sns.calls[0]


def test_aws_adapter_both_channels():
    ses = FakeSesClient()
    sns = FakeSnsClient()
    settings = _settings(ses_from_email="noreply@example.com", notification_sandbox=False)
    adapter = AwsSesSnsNotificationAdapter(settings=settings, ses_client=ses, sns_client=sns)
    message = render_ticket_created(ticket_id="tkt_3")
    results = adapter.deliver(
        message,
        NotificationRecipient(
            phone="+96170123456",
            email="user@example.com",
            preferred_channel="BOTH",
        ),
    )
    assert {item.channel for item in results} == {"SMS", "EMAIL"}
    assert all(item.status == "SUCCEEDED" for item in results)


def test_aws_adapter_invalid_email_is_permanent():
    settings = _settings(ses_from_email="noreply@example.com", notification_sandbox=False)
    adapter = AwsSesSnsNotificationAdapter(
        settings=settings, ses_client=FakeSesClient(), sns_client=FakeSnsClient()
    )
    message = render_ticket_created(ticket_id="tkt_bad_email")
    with pytest.raises(NotificationDeliveryError) as exc_info:
        adapter.deliver(
            message,
            NotificationRecipient(email="bad", preferred_channel="EMAIL"),
        )
    assert exc_info.value.transient is False
    assert exc_info.value.channel_results[0].status == "FAILED_PERMANENT"
    assert exc_info.value.channel_results[0].failure_category == "invalid_recipient"


def test_aws_adapter_sandbox_blocks_non_allowlisted(caplog):
    caplog.set_level(logging.INFO)
    settings = _settings(
        ses_from_email="noreply@example.com",
        notification_sandbox=True,
        notification_allowlist_emails=frozenset({"safe@example.com"}),
        notification_allowlist_phones=frozenset(),
    )
    adapter = AwsSesSnsNotificationAdapter(
        settings=settings, ses_client=FakeSesClient(), sns_client=FakeSnsClient()
    )
    message = render_ticket_created(ticket_id="tkt_sandbox")
    results = adapter.deliver(
        message,
        NotificationRecipient(email="stranger@example.com", preferred_channel="EMAIL"),
    )
    assert results[0].status == "SKIPPED_SANDBOX"
    assert not adapter._ses.calls  # type: ignore[union-attr]


def test_aws_adapter_transient_throttling_releases_for_retry():
    settings = _settings(ses_from_email="noreply@example.com", notification_sandbox=False)
    adapter = AwsSesSnsNotificationAdapter(
        settings=settings,
        ses_client=FakeSesClient(fail_code="Throttling"),
        sns_client=FakeSnsClient(),
    )
    message = render_ticket_created(ticket_id="tkt_throttle")
    with pytest.raises(NotificationDeliveryError) as exc_info:
        adapter.deliver(
            message,
            NotificationRecipient(email="user@example.com", preferred_channel="EMAIL"),
        )
    assert exc_info.value.transient is True


def test_aws_adapter_permanent_provider_reject():
    settings = _settings(ses_from_email="noreply@example.com", notification_sandbox=False)
    adapter = AwsSesSnsNotificationAdapter(
        settings=settings,
        ses_client=FakeSesClient(fail_code="MessageRejected"),
        sns_client=FakeSnsClient(),
    )
    message = render_ticket_created(ticket_id="tkt_reject")
    with pytest.raises(NotificationDeliveryError) as exc_info:
        adapter.deliver(
            message,
            NotificationRecipient(email="user@example.com", preferred_channel="EMAIL"),
        )
    assert exc_info.value.transient is False


def test_destination_throttle_limits_bursts():
    throttle = DestinationThrottle(limit=2, window_seconds=60)
    assert throttle.allow("email:a@b.com")
    assert throttle.allow("email:a@b.com")
    assert throttle.allow("email:a@b.com") is False


def test_emit_records_delivery_and_idempotency(caplog):
    caplog.set_level(logging.INFO)
    settings = _settings(ses_from_email="noreply@example.com", notification_sandbox=False)
    ses = FakeSesClient()
    adapter = AwsSesSnsNotificationAdapter(
        settings=settings, ses_client=ses, sns_client=FakeSnsClient()
    )
    recipient = NotificationRecipient(email="user@example.com", preferred_channel="EMAIL")
    first = emit_ticket_notification(
        event="ticket_created",
        ticket_id="tkt_real_idemp",
        status="SUBMITTED",
        recipient=recipient,
        adapter=adapter,
    )
    second = emit_ticket_notification(
        event="ticket_created",
        ticket_id="tkt_real_idemp",
        status="SUBMITTED",
        recipient=recipient,
        adapter=adapter,
    )
    assert first is True
    assert second is False
    assert len(ses.calls) == 1
    records = notification_delivery_store.list_by_idempotency_key(
        "ticket_created:tkt_real_idemp:SUBMITTED"
    )
    assert len(records) == 1
    assert records[0].channel == "EMAIL"
    assert records[0].attempt_status == "SUCCEEDED"
    assert records[0].provider_message_id == "ses-msg-1"
    assert records[0].destination_hint is not None
    assert "user@example.com" not in records[0].destination_hint


def test_emit_permanent_failure_keeps_claim_and_records():
    settings = _settings(ses_from_email="noreply@example.com", notification_sandbox=False)
    adapter = AwsSesSnsNotificationAdapter(
        settings=settings,
        ses_client=FakeSesClient(fail_code="MessageRejected"),
        sns_client=FakeSnsClient(),
    )
    recipient = NotificationRecipient(email="user@example.com", preferred_channel="EMAIL")
    first = emit_ticket_notification(
        event="ticket_updated",
        ticket_id="tkt_perm_fail",
        status="UNDER_REVIEW",
        recipient=recipient,
        adapter=adapter,
    )
    second = emit_ticket_notification(
        event="ticket_updated",
        ticket_id="tkt_perm_fail",
        status="UNDER_REVIEW",
        recipient=recipient,
        adapter=adapter,
    )
    assert first is False
    # Permanent failure keeps claim → second is duplicate skip, not another send.
    assert second is False
    records = notification_delivery_store.list_by_idempotency_key(
        "ticket_updated:tkt_perm_fail:UNDER_REVIEW"
    )
    assert records
    assert records[0].attempt_status == "FAILED_PERMANENT"


def test_emit_transient_failure_allows_retry():
    settings = _settings(ses_from_email="noreply@example.com", notification_sandbox=False)
    failing = AwsSesSnsNotificationAdapter(
        settings=settings,
        ses_client=FakeSesClient(fail_code="Throttling"),
        sns_client=FakeSnsClient(),
    )
    ok_ses = FakeSesClient()
    ok = AwsSesSnsNotificationAdapter(
        settings=settings, ses_client=ok_ses, sns_client=FakeSnsClient()
    )
    recipient = NotificationRecipient(email="user@example.com", preferred_channel="EMAIL")
    first = emit_ticket_notification(
        event="ticket_resolved",
        ticket_id="tkt_trans_fail",
        status="RESOLVED",
        recipient=recipient,
        adapter=failing,
    )
    second = emit_ticket_notification(
        event="ticket_resolved",
        ticket_id="tkt_trans_fail",
        status="RESOLVED",
        recipient=recipient,
        adapter=ok,
    )
    assert first is False
    assert second is True
    assert len(ok_ses.calls) == 1
