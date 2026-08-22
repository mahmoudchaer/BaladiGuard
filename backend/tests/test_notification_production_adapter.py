from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.notifications.adapters import NotificationDeliveryError
from app.services.notifications.production_adapter import ProductionNotificationAdapter
from app.services.notifications.templates import NotificationMessage


def _adapter() -> ProductionNotificationAdapter:
    adapter = object.__new__(ProductionNotificationAdapter)
    adapter.settings = SimpleNamespace(expo_push_access_token=None)
    return adapter


def _message() -> NotificationMessage:
    return NotificationMessage(
        event="ticket_updated",
        subject="Ticket updated",
        body="Your ticket status changed. Open the safe link for details.",
        ticket_id="tkt_push_test",
        status="IN_PROGRESS",
        status_text="In progress",
        deep_link="https://citizen.example.test/t/ABC234",
    )


def test_expo_push_parses_single_ticket_array(monkeypatch) -> None:
    adapter = _adapter()
    monkeypatch.setattr(
        adapter,
        "_post",
        lambda *_args, **_kwargs: {"data": [{"status": "ok", "id": "expo-ticket-1"}]},
    )

    result = adapter._push(_message(), "ExponentPushToken[device]")

    assert result.status == "SUCCEEDED"
    assert result.provider_message_id == "expo-ticket-1"


def test_expo_push_classifies_device_not_registered_as_permanent(monkeypatch) -> None:
    adapter = _adapter()
    monkeypatch.setattr(
        adapter,
        "_post",
        lambda *_args, **_kwargs: {
            "data": [
                {
                    "status": "error",
                    "message": "Device is not registered",
                    "details": {"error": "DeviceNotRegistered"},
                }
            ]
        },
    )

    result = adapter._push(_message(), "ExponentPushToken[invalid]")

    assert result.status == "FAILED_PERMANENT"
    assert result.failure_category == "invalid_recipient"


@pytest.mark.parametrize("payload", [{}, {"data": {}}, {"data": []}, {"data": ["bad"]}])
def test_expo_push_rejects_malformed_ticket_responses(monkeypatch, payload) -> None:
    adapter = _adapter()
    monkeypatch.setattr(adapter, "_post", lambda *_args, **_kwargs: payload)

    with pytest.raises(NotificationDeliveryError) as exc_info:
        adapter._push(_message(), "ExponentPushToken[device]")

    assert exc_info.value.transient is True
    assert exc_info.value.category == "transient_provider_error"
