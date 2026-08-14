"""Citizen OTP delivery (separate from ticket notification adapter).

Local/mock: OTP codes are available via ``CitizenService.peek_dev_otp_code`` and,
optionally, an explicit stdout helper gated by ``OTP_DEV_PLAINTEXT_STDOUT=true``.
Retained application logs never include verification codes.
Real: publishes an SMS via Amazon SNS when NOTIFICATION_ADAPTER=real.
"""

from __future__ import annotations

import logging
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings, get_settings
from app.utils.phone import PhoneNormalizationError, normalize_phone

logger = logging.getLogger(__name__)


def _mask_phone(phone: str) -> str:
    if len(phone) <= 6:
        return "***"
    return f"{phone[:4]}…{phone[-2:]}"


def _dev_plaintext_stdout_enabled(cfg: Settings) -> bool:
    """Narrow local-only switch; never enabled in production/staging by default."""
    return bool(cfg.otp_dev_plaintext_stdout) and cfg.app_env in {
        "local",
        "development",
        "test",
    }


def _emit_dev_plaintext(canonical: str, code: str, *, reason: str, cfg: Settings) -> None:
    """Print the code to process stdout only when the unsafe-dev switch is on.

    Intentionally avoids the logging framework so codes are not retained with
    application logs (see docs/privacy-lifecycle.md).
    """
    if not _dev_plaintext_stdout_enabled(cfg):
        return
    print(
        f"OTP_DEV_PLAINTEXT phone={_mask_phone(canonical)} reason={reason} code={code}",
        file=sys.stdout,
        flush=True,
    )


def deliver_citizen_otp(
    *,
    phone: str,
    region: str | None,
    code: str,
    settings: Settings | None = None,
) -> None:
    """Deliver a one-time code. Never includes the code in HTTP responses or logs."""
    cfg = settings or get_settings()
    try:
        canonical = normalize_phone(phone, region)
    except PhoneNormalizationError:
        canonical = phone.strip()

    # Mock / test: never hit SNS. Codes stay out of retained logs.
    if cfg.notification_adapter != "real" or cfg.app_env == "test":
        logger.info(
            "Citizen OTP delivery skipped (adapter=%s env=%s) phone=%s",
            cfg.notification_adapter,
            cfg.app_env,
            _mask_phone(canonical),
        )
        _emit_dev_plaintext(canonical, code, reason="mock_or_test", cfg=cfg)
        return

    # Sandbox fails closed: empty allowlist blocks all real SMS destinations.
    if cfg.notification_sandbox:
        allowlist = set(cfg.notification_allowlist_phones)
        if not allowlist or canonical not in allowlist:
            logger.warning(
                "OTP SMS blocked by notification sandbox allowlist phone=%s allowlist_empty=%s",
                _mask_phone(canonical),
                not allowlist,
            )
            _emit_dev_plaintext(canonical, code, reason="sandbox_block", cfg=cfg)
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
        _emit_dev_plaintext(canonical, code, reason="sns_published", cfg=cfg)
    except (BotoCoreError, ClientError):
        logger.exception("Citizen OTP SMS publish failed phone=%s", _mask_phone(canonical))
        # Local-friendly fallback so verify can still be completed while debugging SNS.
        if cfg.app_env in {"local", "development"}:
            _emit_dev_plaintext(canonical, code, reason="sns_publish_failed", cfg=cfg)
            return
        raise
