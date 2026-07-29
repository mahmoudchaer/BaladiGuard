"""Tests for notification delivery orchestration (issue #39)."""

from __future__ import annotations

import logging

import pytest

from app.schemas.ticket import ReportContact
from app.schemas.ticket_response import UpdateTicketStatusRequest
from app.services.complaints.ticket_service import ticket_service
from app.services.notifications import (
    MockNotificationAdapter,
    NotificationDeliveryError,
    NotificationRecipient,
    UnconfiguredRealNotificationAdapter,
    build_notification_adapter,
    emit_ticket_notification,
)
from tests.test_read_tickets import create_ticket


class RecordingAdapter(MockNotificationAdapter):
    def __init__(self) -> None:
        self.calls: list[tuple[str, NotificationRecipient | None]] = []

    def deliver(self, message, recipient=None) -> None:  # type: ignore[no-untyped-def]
        self.calls.append((message.event, recipient))
        super().deliver(message, recipient)


class FailingAdapter(MockNotificationAdapter):
    @property
    def mode(self):
        return "mock"

    def deliver(self, message, recipient=None) -> None:  # type: ignore[no-untyped-def]
        raise NotificationDeliveryError("forced delivery failure")


def test_build_notification_adapter_defaults_to_mock():
    adapter = build_notification_adapter("mock")
    assert adapter.mode == "mock"
    assert isinstance(adapter, MockNotificationAdapter)


def test_build_notification_adapter_real_is_explicitly_unconfigured():
    adapter = build_notification_adapter("real")
    assert adapter.mode == "real"
    assert isinstance(adapter, UnconfiguredRealNotificationAdapter)


def test_emit_success_uses_mock_adapter_and_recipient(caplog):
    caplog.set_level(logging.INFO)
    adapter = RecordingAdapter()
    recipient = NotificationRecipient.from_contact(
        ReportContact(name="Citizen", phone="+96170123456", preferredChannel="SMS")
    )

    delivered = emit_ticket_notification(
        event="ticket_created",
        ticket_id="tkt_notify_success",
        status="SUBMITTED",
        tracking_code="AB23CD",
        ticket_number="BG-2026-0001",
        recipient=recipient,
        adapter=adapter,
    )

    assert delivered is True
    assert len(adapter.calls) == 1
    assert adapter.calls[0][0] == "ticket_created"
    assert adapter.calls[0][1] is not None
    assert adapter.calls[0][1].phone == "+96170123456"
    assert any("Notification mock delivery mode=mock" in r.message for r in caplog.records)
    assert any("recipient_phone=+96170123456" in r.message for r in caplog.records)


def test_emit_skips_duplicate_for_same_event_ticket_status(caplog):
    caplog.set_level(logging.INFO)
    adapter = RecordingAdapter()

    first = emit_ticket_notification(
        event="ticket_updated",
        ticket_id="tkt_notify_dup",
        status="UNDER_REVIEW",
        adapter=adapter,
    )
    second = emit_ticket_notification(
        event="ticket_updated",
        ticket_id="tkt_notify_dup",
        status="UNDER_REVIEW",
        adapter=adapter,
    )

    assert first is True
    assert second is False
    assert len(adapter.calls) == 1
    assert any("Notification skipped duplicate" in r.message for r in caplog.records)


def test_emit_failure_is_logged_and_allows_retry(caplog):
    caplog.set_level(logging.ERROR)
    failing = FailingAdapter()
    recording = RecordingAdapter()

    first = emit_ticket_notification(
        event="ticket_resolved",
        ticket_id="tkt_notify_fail",
        status="CLOSED",
        adapter=failing,
    )
    assert first is False
    assert any("Notification delivery failed" in r.message for r in caplog.records)

    # Failed delivery releases the idempotency claim so retries can succeed.
    second = emit_ticket_notification(
        event="ticket_resolved",
        ticket_id="tkt_notify_fail",
        status="CLOSED",
        adapter=recording,
    )
    assert second is True
    assert len(recording.calls) == 1


def test_status_update_notification_failure_does_not_roll_back_ticket(client, monkeypatch):
    created = create_ticket(client)

    def boom(**_kwargs):
        raise RuntimeError("adapter boom")

    monkeypatch.setattr(
        "app.services.notifications.service.build_notification_adapter",
        lambda: type(
            "Boom",
            (),
            {
                "mode": "mock",
                "deliver": boom,
            },
        )(),
    )

    updated = ticket_service.update_ticket_status(
        created["ticketId"],
        UpdateTicketStatusRequest(status="UNDER_REVIEW"),
    )
    assert updated.status == "UNDER_REVIEW"

    stored = client.get(f"/v1/tickets/{created['ticketId']}")
    assert stored.status_code == 200
    assert stored.json()["status"] == "UNDER_REVIEW"


def test_ticket_create_passes_recipient_into_notification(client, monkeypatch):
    seen: list[NotificationRecipient | None] = []

    def capture(**kwargs):
        seen.append(kwargs.get("recipient"))
        return True

    import app.services.notifications as notifications_pkg

    monkeypatch.setattr(notifications_pkg, "emit_ticket_notification", capture)

    created = create_ticket(client)
    assert created["ticketId"]
    assert seen
    assert seen[0] is not None
    assert seen[0].phone == "+96170123456"
    assert seen[0].email == "citizen@example.com"


def test_recipient_from_contact_requires_phone_or_email():
    assert NotificationRecipient.from_contact(None) is None
    with pytest.raises(ValueError):
        ReportContact(name="Nobody")
