from __future__ import annotations

from app.database.store_factory import get_citizen_store
from app.schemas.citizen import NotificationPreferences, StoredCitizenUser
from app.schemas.stored_ticket import StoredTicket
from app.services.notifications.recipients import ticket_notification_recipient
from tests.conftest import DEFAULT_CITIZEN_PHONE, contribution_ready_auth_headers


def test_legacy_sms_preference_migrates_to_whatsapp() -> None:
    prefs = NotificationPreferences.model_validate({"ticketUpdates": "SMS"})
    assert prefs.whatsapp_enabled is True
    assert prefs.email_enabled is False
    assert prefs.push_enabled is False


def test_push_device_registration_is_multi_device_and_can_be_removed(client) -> None:
    headers = contribution_ready_auth_headers(ticket_updates="NONE")
    first = {
        "deviceId": "device_one",
        "token": "ExponentPushToken[first-device-token]",
        "platform": "ios",
        "appEnvironment": "production",
    }
    second = {
        "deviceId": "device_two",
        "token": "ExponentPushToken[second-device-token]",
        "platform": "android",
        "appEnvironment": "production",
    }
    assert client.put("/v1/citizen/me/push-devices", json=first, headers=headers).status_code == 200
    response = client.put("/v1/citizen/me/push-devices", json=second, headers=headers)
    assert response.status_code == 200
    assert response.json()["pushAvailable"] is True

    deleted = client.delete("/v1/citizen/me/push-devices/device_one", headers=headers)
    assert deleted.status_code == 200
    user = get_citizen_store().get(deleted.json()["userId"])
    assert user is not None
    assert [device.device_id for device in user.push_devices] == ["device_two"]


def test_event_filter_and_channels_are_resolved_together() -> None:
    user = StoredCitizenUser(
        userId="usr_notifications",
        phone=DEFAULT_CITIZEN_PHONE,
        phoneVerifiedAt="2026-01-01T00:00:00Z",
        email="citizen@example.com",
        notificationPreferences={
            "preferenceVersion": 2,
            "emailEnabled": True,
            "whatsAppEnabled": True,
            "statusChanges": False,
        },
        createdAt="2026-01-01T00:00:00Z",
        updatedAt="2026-01-01T00:00:00Z",
    )
    ticket = StoredTicket.model_construct(
        ticket_id="tkt_notifications",
        owner_user_id=user.user_id,
        contact=None,
    )

    class Lookup:
        def get(self, _user_id: str):
            return user

    assert (
        ticket_notification_recipient(ticket, citizen_lookup=Lookup(), event="ticket_updated")
        is None
    )
    recipient = ticket_notification_recipient(
        ticket, citizen_lookup=Lookup(), event="ticket_created"
    )
    assert recipient is not None
    assert recipient.channels == ("EMAIL", "WHATSAPP")
