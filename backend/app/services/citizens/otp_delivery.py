"""Citizen OTP delivery (separate from ticket notification adapter).

Local/mock: prints the code to server logs so developers can complete the flow.
Real: publishes an SMS via Amazon SNS when NOTIFICATION_ADAPTER=real.
"""

from __future__ import annotations

import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings, get_settings
from app.utils.phone import PhoneNormalizationError, normalize_phone

logger = logging.getLogger(__name__)


def _mask_phone(phone: str) -> str:
    if len(phone) <= 6:
        return "***"
    return f"{phone[:4]}…{phone[-2:]}"


def deliver_citizen_otp(
    *,
    phone: str,
    region: str | None,
    code: str,
    settings: Settings | None = None,
) -> None:
    """Deliver a one-time code. Never includes the code in HTTP responses."""
    cfg = settings or get_settings()
    try:
        canonical = normalize_phone(phone, region)
    except PhoneNormalizationError:
        canonical = phone.strip()

    # Mock / test: never hit SNS — print the code in server logs only.
    if cfg.notification_adapter != "real" or cfg.app_env == "test":
        logger.warning(
            "LOCAL OTP (not SMS) phone=%s code=%s — enter this code in the app",
            _mask_phone(canonical),
            code,
        )
        return

    # Sandbox: only allowlisted E.164 numbers receive SMS.
    if cfg.notification_sandbox and cfg.notification_allowlist_phones:
        if canonical not in set(cfg.notification_allowlist_phones):
            logger.warning(
                "OTP SMS blocked by notification sandbox allowlist phone=%s",
                _mask_phone(canonical),
            )
            if cfg.app_env in {"local", "development"}:
                logger.warning(
                    "LOCAL OTP FALLBACK phone=%s code=%s",
                    _mask_phone(canonical),
                    code,
                )
            return

    client = boto3.client("sns", region_name=cfg.aws_region)
    message = f"BaladiGuard verification code: {code}. It expires in 5 minutes."
    attributes: dict[str, dict[str, str]] = {
        "AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"},
    }
    if cfg.sns_sms_sender_id:
        attributes["AWS.SNS.SMS.SenderID"] = {
            "DataType": "String",
            "StringValue": cfg.sns_sms_sender_id,
        }

    try:
        client.publish(PhoneNumber=canonical, Message=message, MessageAttributes=attributes)
        logger.info("Citizen OTP SMS published phone=%s", _mask_phone(canonical))
    except (BotoCoreError, ClientError):
        logger.exception("Citizen OTP SMS publish failed phone=%s", _mask_phone(canonical))
        # Local-friendly fallback so verify can still be completed while debugging SNS.
        if cfg.app_env in {"local", "development"}:
            logger.warning(
                "LOCAL OTP FALLBACK phone=%s code=%s",
                _mask_phone(canonical),
                code,
            )
            return
        raise

    # SNS Publish can succeed while carriers still drop delivery (common for Lebanon
    # without a registered Sender ID). Mirror the code in local/dev logs so auth works.
    if cfg.app_env in {"local", "development"}:
        logger.warning(
            "LOCAL OTP MIRROR phone=%s code=%s — enter this code if SMS does not arrive",
            _mask_phone(canonical),
            code,
        )
