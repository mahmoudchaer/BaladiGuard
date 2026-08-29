"""Notification channel delivery results (issue #183)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DeliveryChannel = Literal["EMAIL", "SMS", "WHATSAPP", "PUSH"]
DeliveryAttemptStatus = Literal[
    "SUCCEEDED",
    "FAILED_TRANSIENT",
    "FAILED_PERMANENT",
    "SKIPPED_SANDBOX",
    "SKIPPED_INVALID",
    "SKIPPED_THROTTLED",
    "SKIPPED_OPT_OUT",
]

# Permanent categories (safe for logs; never secrets).
FAILURE_INVALID_RECIPIENT = "invalid_recipient"
FAILURE_PROVIDER_REJECTED = "provider_rejected"
FAILURE_NOT_CONFIGURED = "not_configured"
FAILURE_SANDBOX_BLOCKED = "sandbox_blocked"
FAILURE_THROTTLED = "throttled"
FAILURE_TRANSIENT = "transient_provider_error"
FAILURE_UNKNOWN = "unknown"


def redact_email(email: str | None) -> str | None:
    if not email:
        return None
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    head = local[:1] if local else "*"
    return f"{head}***@{domain}"


def redact_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    import re

    digits = re.sub(r"\D", "", phone)
    if len(digits) <= 4:
        return "***"
    return f"+***{digits[-4:]}"


@dataclass(frozen=True, slots=True)
class ChannelDeliveryResult:
    channel: DeliveryChannel
    status: DeliveryAttemptStatus
    provider_message_id: str | None = None
    failure_category: str | None = None
