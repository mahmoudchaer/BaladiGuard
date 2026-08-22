"""Production fan-out for ordinary citizen ticket updates (issue #317)."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.services.notifications.adapters import NotificationDeliveryError, NotificationRecipient
from app.services.notifications.aws_adapter import AwsSesSnsNotificationAdapter
from app.services.notifications.results import ChannelDeliveryResult
from app.services.notifications.templates import NotificationMessage


class ProductionNotificationAdapter:
    """Fan out only to explicitly selected channels; ordinary SMS is never implicit."""

    mode = "real"

    def __init__(self, *, settings) -> None:
        self.settings = settings
        self.email = AwsSesSnsNotificationAdapter(settings=settings)

    @staticmethod
    def _post(url: str, payload: dict, headers: dict[str, str]) -> dict:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed provider URLs
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            transient = exc.code == 429 or exc.code >= 500
            raise NotificationDeliveryError(
                "Notification provider rejected the request.",
                category="provider_rejected",
                transient=transient,
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise NotificationDeliveryError(
                "Notification provider is temporarily unavailable.",
                category="transient_provider_error",
                transient=True,
            ) from exc

    def _whatsapp(self, message: NotificationMessage, phone: str) -> ChannelDeliveryResult:
        if not self.settings.whatsapp_phone_number_id or not self.settings.whatsapp_access_token:
            return ChannelDeliveryResult(
                channel="WHATSAPP", status="FAILED_PERMANENT", failure_category="not_configured"
            )
        url = (
            f"https://graph.facebook.com/{self.settings.whatsapp_graph_api_version}/"
            f"{self.settings.whatsapp_phone_number_id}/messages"
        )
        data = self._post(
            url,
            {
                "messaging_product": "whatsapp",
                "to": phone.lstrip("+"),
                "type": "template",
                "template": {
                    "name": self.settings.notification_whatsapp_template_name,
                    "language": {"code": self.settings.notification_whatsapp_template_language},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": message.ticket_id},
                                {"type": "text", "text": message.status},
                            ],
                        }
                    ],
                },
            },
            {"Authorization": f"Bearer {self.settings.whatsapp_access_token}"},
        )
        message_id = ((data.get("messages") or [{}])[0]).get("id")
        return ChannelDeliveryResult(
            channel="WHATSAPP", status="SUCCEEDED", provider_message_id=message_id
        )

    def _push(self, message: NotificationMessage, token: str) -> ChannelDeliveryResult:
        headers = {}
        if self.settings.expo_push_access_token:
            headers["Authorization"] = f"Bearer {self.settings.expo_push_access_token}"
        data = self._post(
            "https://exp.host/--/api/v2/push/send",
            {
                "to": token,
                "title": message.subject,
                "body": message.body,
                "data": {"url": message.deep_link},
                "sound": "default",
            },
            headers,
        )
        ticket_payload = data.get("data")
        if (
            not isinstance(ticket_payload, list)
            or len(ticket_payload) != 1
            or not isinstance(ticket_payload[0], dict)
        ):
            raise NotificationDeliveryError(
                "Expo Push API returned a malformed ticket response.",
                category="transient_provider_error",
                transient=True,
            )
        ticket = ticket_payload[0]
        if ticket.get("status") == "error":
            details = ticket.get("details") or {}
            permanent = details.get("error") == "DeviceNotRegistered"
            return ChannelDeliveryResult(
                channel="PUSH",
                status="FAILED_PERMANENT" if permanent else "FAILED_TRANSIENT",
                failure_category="invalid_recipient" if permanent else "provider_rejected",
            )
        return ChannelDeliveryResult(
            channel="PUSH", status="SUCCEEDED", provider_message_id=ticket.get("id")
        )

    def deliver(
        self, message: NotificationMessage, recipient: NotificationRecipient | None = None
    ) -> list[ChannelDeliveryResult]:
        if recipient is None:
            raise NotificationDeliveryError(
                "No eligible destination.", category="invalid_recipient"
            )
        channels = recipient.channels or ((recipient.preferred_channel or "").upper(),)
        results: list[ChannelDeliveryResult] = []
        if "EMAIL" in channels and recipient.email:
            try:
                results.extend(
                    self.email.deliver(
                        message,
                        NotificationRecipient(email=recipient.email, preferred_channel="EMAIL"),
                    )
                )
            except NotificationDeliveryError as exc:
                results.extend(
                    exc.channel_results
                    or [
                        ChannelDeliveryResult(
                            channel="EMAIL",
                            status=("FAILED_TRANSIENT" if exc.transient else "FAILED_PERMANENT"),
                            failure_category=exc.category,
                        )
                    ]
                )
        if "WHATSAPP" in channels and recipient.phone:
            try:
                results.append(self._whatsapp(message, recipient.phone))
            except NotificationDeliveryError as exc:
                results.append(
                    ChannelDeliveryResult(
                        channel="WHATSAPP",
                        status="FAILED_TRANSIENT" if exc.transient else "FAILED_PERMANENT",
                        failure_category=exc.category,
                    )
                )
        if "PUSH" in channels:
            for token in recipient.push_tokens:
                try:
                    results.append(self._push(message, token))
                except NotificationDeliveryError as exc:
                    results.append(
                        ChannelDeliveryResult(
                            channel="PUSH",
                            status="FAILED_TRANSIENT" if exc.transient else "FAILED_PERMANENT",
                            failure_category=exc.category,
                        )
                    )
        return results
