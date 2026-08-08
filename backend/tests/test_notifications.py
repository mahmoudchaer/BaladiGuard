"""Tests for notification delivery orchestration (issue #39)."""

from __future__ import annotations

import logging

import pytest

from app.database.memory import ticket_store
from app.database.memory_citizen import citizen_store
from app.schemas.citizen import CitizenProfileUpdateRequest
from app.schemas.ticket import ReportContact
from app.schemas.ticket_response import UpdateTicketStatusRequest
from app.services.citizens.service import citizen_service
from app.services.complaints.ticket_service import ticket_service
from app.services.notifications import (
    MockNotificationAdapter,
    NotificationDeliveryError,
    NotificationRecipient,
    UnconfiguredRealNotificationAdapter,
    build_notification_adapter,
    emit_ticket_notification,
)
from tests.conftest import (
    DEFAULT_CITIZEN_EMAIL,
    DEFAULT_CITIZEN_PHONE,
    contribution_ready_auth_headers,
    ensure_contribution_ready_citizen,
)
from tests.test_read_tickets import create_ticket
from tests.test_submit_ticket import VALID_PAYLOAD


class RecordingAdapter(MockNotificationAdapter):
    def __init__(self) -> None:
        self.calls: list[tuple[str, NotificationRecipient | None]] = []

    def deliver(self, message, recipient=None):  # type: ignore[no-untyped-def]
        self.calls.append((message.event, recipient))
        return super().deliver(message, recipient)


class FailingAdapter(MockNotificationAdapter):
    @property
    def mode(self):
        return "mock"

    def deliver(self, message, recipient=None) -> None:  # type: ignore[no-untyped-def]
        # transient=True releases the idempotency claim so later retries can succeed.
        raise NotificationDeliveryError("forced delivery failure", transient=True)


def test_build_notification_adapter_defaults_to_mock():
    adapter = build_notification_adapter("mock")
    assert adapter.mode == "mock"
    assert isinstance(adapter, MockNotificationAdapter)


def test_build_notification_adapter_real_without_channels_is_unconfigured(monkeypatch):
    monkeypatch.setenv("SES_FROM_EMAIL", "")
    monkeypatch.setenv("NOTIFICATION_ALLOW_SMS_ONLY_REAL", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    adapter = build_notification_adapter("real")
    assert adapter.mode == "real"
    assert isinstance(adapter, UnconfiguredRealNotificationAdapter)
    get_settings.cache_clear()


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
    # Raw phone must never appear in logs; only a redacted hint is allowed.
    assert not any("+96170123456" in r.message for r in caplog.records)
    assert any("recipient_phone=+***3456" in r.message for r in caplog.records)


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

    # Transient failure releases the idempotency claim so retries can succeed.
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
    assert seen[0].email is None
    assert seen[0].preferred_channel == "SMS"


@pytest.mark.parametrize(
    ("ticket_updates", "expected_phone", "expected_email", "expected_channel"),
    [
        ("SMS", DEFAULT_CITIZEN_PHONE, None, "SMS"),
        ("EMAIL", None, DEFAULT_CITIZEN_EMAIL, "EMAIL"),
        ("BOTH", DEFAULT_CITIZEN_PHONE, DEFAULT_CITIZEN_EMAIL, "BOTH"),
    ],
)
def test_account_linked_ticket_notifications_use_live_profile_preferences(
    client,
    monkeypatch,
    ticket_updates,
    expected_phone,
    expected_email,
    expected_channel,
):
    adapter = RecordingAdapter()
    monkeypatch.setattr(
        "app.services.notifications.service.build_notification_adapter",
        lambda: adapter,
    )

    headers = contribution_ready_auth_headers(ticket_updates=ticket_updates)
    created = client.post("/v1/tickets", json=VALID_PAYLOAD, headers=headers)
    assert created.status_code == 201, created.text

    assert adapter.calls[-1][0] == "ticket_created"
    created_recipient = adapter.calls[-1][1]
    assert created_recipient is not None
    assert created_recipient.phone == expected_phone
    assert created_recipient.email == expected_email
    assert created_recipient.preferred_channel == expected_channel

    updated = client.patch(
        f"/v1/tickets/{created.json()['ticketId']}/status",
        json={"status": "UNDER_REVIEW"},
    )
    assert updated.status_code == 200, updated.text

    assert adapter.calls[-1][0] == "ticket_updated"
    updated_recipient = adapter.calls[-1][1]
    assert updated_recipient is not None
    assert updated_recipient.phone == expected_phone
    assert updated_recipient.email == expected_email
    assert updated_recipient.preferred_channel == expected_channel


def test_account_linked_ticket_notifications_honor_later_opt_out(client, monkeypatch):
    adapter = RecordingAdapter()
    monkeypatch.setattr(
        "app.services.notifications.service.build_notification_adapter",
        lambda: adapter,
    )
    user, token = ensure_contribution_ready_citizen(ticket_updates="SMS")

    created = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201, created.text
    assert len(adapter.calls) == 1

    citizen_service.update_profile(
        user.user_id,
        CitizenProfileUpdateRequest.model_validate(
            {"notificationPreferences": {"ticketUpdates": "NONE"}}
        ),
    )

    updated = client.patch(
        f"/v1/tickets/{created.json()['ticketId']}/status",
        json={"status": "UNDER_REVIEW"},
    )

    assert updated.status_code == 200, updated.text
    assert len(adapter.calls) == 1


def test_account_linked_ticket_notifications_skip_missing_profile(client, monkeypatch):
    adapter = RecordingAdapter()
    monkeypatch.setattr(
        "app.services.notifications.service.build_notification_adapter",
        lambda: adapter,
    )
    user, token = ensure_contribution_ready_citizen(ticket_updates="SMS")

    created = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201, created.text
    assert len(adapter.calls) == 1

    citizen_store.clear()
    updated = client.patch(
        f"/v1/tickets/{created.json()['ticketId']}/status",
        json={"status": "UNDER_REVIEW"},
    )

    assert updated.status_code == 200, updated.text
    assert len(adapter.calls) == 1
    assert ticket_store.get(created.json()["ticketId"]).owner_user_id == user.user_id


def test_legacy_unowned_ticket_notifications_use_contact_snapshot(client, monkeypatch):
    adapter = RecordingAdapter()
    monkeypatch.setattr(
        "app.services.notifications.service.build_notification_adapter",
        lambda: adapter,
    )
    user, token = ensure_contribution_ready_citizen(ticket_updates="SMS")

    created = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["ticketId"]
    assert len(adapter.calls) == 1

    stored = ticket_store.get(ticket_id)
    assert stored is not None
    ticket_store.save(stored.model_copy(update={"owner_user_id": None}))
    citizen_service.update_profile(
        user.user_id,
        CitizenProfileUpdateRequest.model_validate(
            {"notificationPreferences": {"ticketUpdates": "NONE"}}
        ),
    )

    updated = client.patch(
        f"/v1/tickets/{ticket_id}/status",
        json={"status": "UNDER_REVIEW"},
    )

    assert updated.status_code == 200, updated.text
    assert len(adapter.calls) == 2
    _event, recipient = adapter.calls[-1]
    assert recipient is not None
    assert recipient.phone == DEFAULT_CITIZEN_PHONE
    assert recipient.email == DEFAULT_CITIZEN_EMAIL
    assert recipient.preferred_channel == "SMS"


def test_recipient_from_contact_requires_phone_or_email():
    assert NotificationRecipient.from_contact(None) is None
    with pytest.raises(ValueError):
        ReportContact(name="Nobody")


def test_dynamodb_claim_is_atomic_across_two_workers(dynamodb_settings):
    """Two worker ledgers sharing DynamoDB cannot both claim the same key."""
    from concurrent.futures import ThreadPoolExecutor

    from app.config import Settings
    from app.services.notifications.ledger import DynamoNotificationDeliveryLedger

    assert isinstance(dynamodb_settings, Settings)
    key = "ticket_updated:tkt_notify_race:UNDER_REVIEW"
    workers = [
        DynamoNotificationDeliveryLedger(dynamodb_settings),
        DynamoNotificationDeliveryLedger(dynamodb_settings),
    ]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda ledger: ledger.claim(key), workers))

    assert sorted(results) == [False, True]
    # Loser still cannot claim after the winner holds it.
    assert workers[0].claim(key) is False
    assert workers[1].claim(key) is False


def test_two_dynamodb_workers_cannot_both_emit_same_notification(
    dynamodb_settings,
    monkeypatch,
):
    """Simulate two API instances: only the first durable claim may deliver."""
    from app.services.notifications import service as notification_service
    from app.services.notifications.ledger import DynamoNotificationDeliveryLedger

    worker_a = DynamoNotificationDeliveryLedger(dynamodb_settings)
    worker_b = DynamoNotificationDeliveryLedger(dynamodb_settings)
    adapter = RecordingAdapter()

    monkeypatch.setattr(notification_service, "get_delivery_ledger", lambda: worker_a)
    first = emit_ticket_notification(
        event="ticket_updated",
        ticket_id="tkt_notify_multi_worker",
        status="UNDER_REVIEW",
        adapter=adapter,
    )

    monkeypatch.setattr(notification_service, "get_delivery_ledger", lambda: worker_b)
    second = emit_ticket_notification(
        event="ticket_updated",
        ticket_id="tkt_notify_multi_worker",
        status="UNDER_REVIEW",
        adapter=adapter,
    )

    assert first is True
    assert second is False
    assert len(adapter.calls) == 1
