"""Amazon SES email + SNS SMS notification delivery (issue #183).

Credentials use the standard AWS chain (IAM role / env keys). Never log secrets,
message bodies with staff data, or full citizen contact when avoidable.
"""

from __future__ import annotations

import logging
import re
import time
from email.utils import parseaddr
from threading import Lock
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings, get_settings
from app.services.notifications.adapters import (
    NotificationDeliveryError,
    NotificationRecipient,
)
from app.services.notifications.results import (
    FAILURE_INVALID_RECIPIENT,
    FAILURE_NOT_CONFIGURED,
    FAILURE_PROVIDER_REJECTED,
    FAILURE_SANDBOX_BLOCKED,
    FAILURE_THROTTLED,
    FAILURE_TRANSIENT,
    FAILURE_UNKNOWN,
    ChannelDeliveryResult,
    redact_email,
    redact_phone,
)
from app.services.notifications.templates import NotificationMessage
from app.utils.phone import PhoneNormalizationError, normalize_phone

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Provider error codes treated as temporary (safe to retry).
_TRANSIENT_ERROR_CODES = frozenset(
    {
        "Throttling",
        "ThrottlingException",
        "TooManyRequestsException",
        "ServiceUnavailable",
        "ServiceUnavailableException",
        "RequestTimeout",
        "RequestTimeoutException",
        "InternalFailure",
        "InternalError",
        "PriorRequestNotComplete",
        "LimitExceededException",
    }
)


def is_valid_email(email: str | None) -> bool:
    if not email or not str(email).strip():
        return False
    _, addr = parseaddr(str(email).strip())
    candidate = addr or str(email).strip()
    return bool(_EMAIL_RE.match(candidate)) and len(candidate) <= 254


def is_valid_e164_phone(phone: str | None) -> bool:
    if not phone or not str(phone).strip():
        return False
    try:
        normalize_phone(str(phone).strip())
        return True
    except PhoneNormalizationError:
        return False


class DestinationThrottle:
    """Simple per-destination fixed window throttle (process-local)."""

    def __init__(self, *, limit: int = 10, window_seconds: int = 60) -> None:
        self.limit = max(1, limit)
        self.window_seconds = max(1, window_seconds)
        self._lock = Lock()
        self._buckets: dict[str, tuple[int, float]] = {}

    def allow(self, destination_key: str, *, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        window_start = int(current // self.window_seconds) * self.window_seconds
        key = f"{destination_key}:{window_start}"
        with self._lock:
            count, _ = self._buckets.get(key, (0, float(window_start + self.window_seconds)))
            if count >= self.limit:
                return False
            self._buckets[key] = (count + 1, float(window_start + self.window_seconds))
            # Opportunistic prune of old windows.
            if len(self._buckets) > 500:
                stale = [k for k, (_, reset) in self._buckets.items() if reset < current]
                for old in stale[:200]:
                    self._buckets.pop(old, None)
            return True


class AwsSesSnsNotificationAdapter:
    """Production channel adapter: SES email + SNS SMS."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        ses_client: Any | None = None,
        sns_client: Any | None = None,
        throttle: DestinationThrottle | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._ses = ses_client
        self._sns = sns_client
        self._throttle = throttle or DestinationThrottle(
            limit=self._settings.notification_destination_rate_limit,
            window_seconds=self._settings.notification_destination_rate_window_seconds,
        )

    @property
    def mode(self) -> str:
        return "real"

    def _boto_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"region_name": self._settings.aws_region}
        # Prefer IAM role; optional explicit keys for local (never log them).
        import os

        access_key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
        secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key
        return kwargs

    def _ses_client(self):
        if self._ses is None:
            self._ses = boto3.client("ses", **self._boto_kwargs())
        return self._ses

    def _sns_client(self):
        if self._sns is None:
            self._sns = boto3.client("sns", **self._boto_kwargs())
        return self._sns

    def _channels_for(self, recipient: NotificationRecipient | None) -> list[str]:
        if recipient is None:
            return []
        preference = (recipient.preferred_channel or "").strip().upper()
        if preference == "SMS":
            return ["SMS"]
        if preference == "EMAIL":
            return ["EMAIL"]
        if preference == "BOTH":
            channels: list[str] = []
            if recipient.phone:
                channels.append("SMS")
            if recipient.email:
                channels.append("EMAIL")
            return channels
        # Legacy / snapshot: prefer SMS when both present, otherwise whichever exists.
        if recipient.phone and not recipient.email:
            return ["SMS"]
        if recipient.email and not recipient.phone:
            return ["EMAIL"]
        if recipient.phone and recipient.email:
            return ["SMS"]  # snapshot preferredChannel often SMS
        return []

    def _sandbox_allows_email(self, email: str) -> bool:
        if not self._settings.notification_sandbox:
            return True
        allowed = self._settings.notification_allowlist_emails
        return email.strip().lower() in allowed

    def _sandbox_allows_phone(self, phone: str) -> bool:
        if not self._settings.notification_sandbox:
            return True
        try:
            normalized = normalize_phone(phone)
        except PhoneNormalizationError:
            return False
        allowed = self._settings.notification_allowlist_phones
        return normalized in allowed

    def _classify_client_error(self, exc: ClientError) -> tuple[bool, str]:
        code = (exc.response.get("Error") or {}).get("Code", "") or ""
        if code in _TRANSIENT_ERROR_CODES or code.endswith("Throttling"):
            return True, FAILURE_TRANSIENT if "Throttl" not in code else FAILURE_THROTTLED
        if code in {
            "MessageRejected",
            "InvalidParameterValue",
            "InvalidParameter",
            "ValidationError",
            "MailFromDomainNotVerified",
            "ConfigurationSetDoesNotExist",
            "AccountSendingPausedException",
        }:
            return False, FAILURE_PROVIDER_REJECTED
        return False, FAILURE_UNKNOWN

    def _send_email(self, message: NotificationMessage, email: str) -> ChannelDeliveryResult:
        if not is_valid_email(email):
            return ChannelDeliveryResult(
                channel="EMAIL",
                status="FAILED_PERMANENT",
                failure_category=FAILURE_INVALID_RECIPIENT,
            )
        if not self._sandbox_allows_email(email):
            logger.info(
                "Notification sandbox blocked email destination_hint=%s ticket_id=%s",
                redact_email(email),
                message.ticket_id,
            )
            return ChannelDeliveryResult(
                channel="EMAIL",
                status="SKIPPED_SANDBOX",
                failure_category=FAILURE_SANDBOX_BLOCKED,
            )
        from_address = self._settings.ses_from_email
        if not from_address:
            return ChannelDeliveryResult(
                channel="EMAIL",
                status="FAILED_PERMANENT",
                failure_category=FAILURE_NOT_CONFIGURED,
            )
        if not self._throttle.allow(f"email:{email.strip().lower()}"):
            return ChannelDeliveryResult(
                channel="EMAIL",
                status="SKIPPED_THROTTLED",
                failure_category=FAILURE_THROTTLED,
            )

        try:
            params: dict[str, Any] = {
                "Source": from_address,
                "Destination": {"ToAddresses": [email.strip()]},
                "Message": {
                    "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": message.body, "Charset": "UTF-8"}},
                },
            }
            if self._settings.ses_configuration_set:
                params["ConfigurationSetName"] = self._settings.ses_configuration_set
            response = self._ses_client().send_email(**params)
            message_id = response.get("MessageId")
            logger.info(
                "Notification email sent ticket_id=%s event=%s destination_hint=%s "
                "provider_message_id=%s",
                message.ticket_id,
                message.event,
                redact_email(email),
                message_id,
            )
            return ChannelDeliveryResult(
                channel="EMAIL",
                status="SUCCEEDED",
                provider_message_id=str(message_id) if message_id else None,
            )
        except ClientError as exc:
            transient, category = self._classify_client_error(exc)
            logger.error(
                "Notification email provider error ticket_id=%s category=%s code=%s",
                message.ticket_id,
                category,
                (exc.response.get("Error") or {}).get("Code"),
            )
            return ChannelDeliveryResult(
                channel="EMAIL",
                status="FAILED_TRANSIENT" if transient else "FAILED_PERMANENT",
                failure_category=category,
            )
        except BotoCoreError:
            logger.error(
                "Notification email transport error ticket_id=%s category=%s",
                message.ticket_id,
                FAILURE_TRANSIENT,
            )
            return ChannelDeliveryResult(
                channel="EMAIL",
                status="FAILED_TRANSIENT",
                failure_category=FAILURE_TRANSIENT,
            )

    def _send_sms(self, message: NotificationMessage, phone: str) -> ChannelDeliveryResult:
        if not is_valid_e164_phone(phone):
            return ChannelDeliveryResult(
                channel="SMS",
                status="FAILED_PERMANENT",
                failure_category=FAILURE_INVALID_RECIPIENT,
            )
        try:
            normalized = normalize_phone(phone)
        except PhoneNormalizationError:
            return ChannelDeliveryResult(
                channel="SMS",
                status="FAILED_PERMANENT",
                failure_category=FAILURE_INVALID_RECIPIENT,
            )
        if not self._sandbox_allows_phone(normalized):
            logger.info(
                "Notification sandbox blocked sms destination_hint=%s ticket_id=%s",
                redact_phone(normalized),
                message.ticket_id,
            )
            return ChannelDeliveryResult(
                channel="SMS",
                status="SKIPPED_SANDBOX",
                failure_category=FAILURE_SANDBOX_BLOCKED,
            )
        if not self._throttle.allow(f"sms:{normalized}"):
            return ChannelDeliveryResult(
                channel="SMS",
                status="SKIPPED_THROTTLED",
                failure_category=FAILURE_THROTTLED,
            )

        # SMS body only — subject would bloat cost; templates already put essentials in body.
        sms_body = message.body
        if len(sms_body) > 600:
            sms_body = sms_body[:597] + "..."

        try:
            params: dict[str, Any] = {
                "PhoneNumber": normalized,
                "Message": sms_body,
            }
            attributes: dict[str, dict[str, str]] = {
                "AWS.SNS.SMS.SMSType": {
                    "DataType": "String",
                    "StringValue": "Transactional",
                }
            }
            if self._settings.sns_sms_sender_id:
                attributes["AWS.SNS.SMS.SenderID"] = {
                    "DataType": "String",
                    "StringValue": self._settings.sns_sms_sender_id,
                }
            params["MessageAttributes"] = attributes
            response = self._sns_client().publish(**params)
            message_id = response.get("MessageId")
            logger.info(
                "Notification sms sent ticket_id=%s event=%s destination_hint=%s "
                "provider_message_id=%s",
                message.ticket_id,
                message.event,
                redact_phone(normalized),
                message_id,
            )
            return ChannelDeliveryResult(
                channel="SMS",
                status="SUCCEEDED",
                provider_message_id=str(message_id) if message_id else None,
            )
        except ClientError as exc:
            transient, category = self._classify_client_error(exc)
            logger.error(
                "Notification sms provider error ticket_id=%s category=%s code=%s",
                message.ticket_id,
                category,
                (exc.response.get("Error") or {}).get("Code"),
            )
            return ChannelDeliveryResult(
                channel="SMS",
                status="FAILED_TRANSIENT" if transient else "FAILED_PERMANENT",
                failure_category=category,
            )
        except BotoCoreError:
            logger.error(
                "Notification sms transport error ticket_id=%s category=%s",
                message.ticket_id,
                FAILURE_TRANSIENT,
            )
            return ChannelDeliveryResult(
                channel="SMS",
                status="FAILED_TRANSIENT",
                failure_category=FAILURE_TRANSIENT,
            )

    def deliver(
        self,
        message: NotificationMessage,
        recipient: NotificationRecipient | None = None,
    ) -> list[ChannelDeliveryResult]:
        channels = self._channels_for(recipient)
        if not channels:
            raise NotificationDeliveryError(
                f"No deliverable channel for ticket {message.ticket_id}.",
                category=FAILURE_INVALID_RECIPIENT,
                transient=False,
            )

        results: list[ChannelDeliveryResult] = []
        for channel in channels:
            if channel == "EMAIL":
                results.append(self._send_email(message, recipient.email or ""))
            elif channel == "SMS":
                results.append(self._send_sms(message, recipient.phone or ""))

        had_success = any(item.status == "SUCCEEDED" for item in results)
        hard_fail = any(item.status in {"FAILED_PERMANENT", "FAILED_TRANSIENT"} for item in results)
        only_skips = results and all(item.status.startswith("SKIPPED_") for item in results)

        if had_success:
            return results

        if only_skips:
            # Sandbox / invalid skips: keep results so the service can record them.
            # Throttle-only: transient so callers may retry. Pure sandbox: treat as
            # non-transient policy outcome (ledger keeps claim; no real citizen hit).
            throttle_only = all(item.status == "SKIPPED_THROTTLED" for item in results)
            sandbox_only = all(item.status == "SKIPPED_SANDBOX" for item in results)
            category = results[0].failure_category or FAILURE_SANDBOX_BLOCKED
            if sandbox_only:
                # Recorded as complete for idempotency; no external message sent.
                return results
            raise NotificationDeliveryError(
                f"Notification delivery skipped for ticket {message.ticket_id} ({category}).",
                category=category,
                transient=throttle_only,
                channel_results=results,
            )

        if hard_fail:
            transient = any(item.status == "FAILED_TRANSIENT" for item in results)
            category = next(
                (item.failure_category for item in results if item.failure_category is not None),
                FAILURE_UNKNOWN,
            )
            raise NotificationDeliveryError(
                f"Notification delivery failed for ticket {message.ticket_id} ({category}).",
                category=category or FAILURE_UNKNOWN,
                transient=transient,
                channel_results=results,
            )

        return results
