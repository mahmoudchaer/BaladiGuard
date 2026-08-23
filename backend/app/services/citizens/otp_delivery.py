"""Citizen OTP delivery providers (issue #297).

Separates OTP transport from ticket ``NOTIFICATION_ADAPTER``. Channels:
``mock`` | ``sns`` | ``whatsapp``. Exactly one provider is used per request.
"""

from __future__ import annotations

import base64
import json
import logging
import sys
from typing import Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings, get_settings
from app.core.metrics import emit_metric
from app.utils.phone import PhoneNormalizationError, normalize_phone

logger = logging.getLogger(__name__)

OtpDeliveryChannel = Literal["mock", "sns", "whatsapp", "twilio"]
PublicOtpDeliveryChannel = Literal["sms", "whatsapp", "dev"]


class OtpDeliveryError(RuntimeError):
    """Provider failure that should invalidate the unused OTP challenge."""

    def __init__(self, category: str, message: str = "OTP delivery failed.") -> None:
        super().__init__(message)
        self.category = category


class OtpVerificationError(RuntimeError):
    """Safe Twilio Verify check failure; no raw provider detail reaches callers."""

    def __init__(self, category: str) -> None:
        super().__init__("OTP verification failed.")
        self.category = category


def _mask_phone(phone: str) -> str:
    if len(phone) <= 6:
        return "***"
    return f"{phone[:4]}…{phone[-2:]}"


def _dev_plaintext_stdout_enabled(cfg: Settings) -> bool:
    return bool(cfg.otp_dev_plaintext_stdout) and cfg.app_env in {
        "local",
        "development",
        "test",
    }


def _emit_dev_plaintext(canonical: str, code: str, *, reason: str, cfg: Settings) -> None:
    if not _dev_plaintext_stdout_enabled(cfg):
        return
    print(
        f"OTP_DEV_PLAINTEXT phone={_mask_phone(canonical)} reason={reason} code={code}",
        file=sys.stdout,
        flush=True,
    )


def resolve_citizen_otp_delivery_channel(cfg: Settings) -> OtpDeliveryChannel:
    """Resolve channel. Explicit env wins; otherwise preserve historical SNS/mock behavior."""
    raw = (cfg.citizen_otp_delivery_channel or "").strip().lower()
    if raw in {"mock", "sns", "whatsapp", "twilio"}:
        return raw  # type: ignore[return-value]
    # Legacy default: mock unless ticket notifications already use real SNS path.
    if cfg.app_env == "test" or cfg.notification_adapter != "real":
        return "mock"
    return "sns"


def public_otp_delivery_channel(channel: OtpDeliveryChannel) -> PublicOtpDeliveryChannel:
    if channel == "whatsapp":
        return "whatsapp"
    if channel in {"sns", "twilio"}:
        return "sms"
    return "dev"


class CitizenOtpDeliveryProvider(Protocol):
    def deliver(self, *, canonical_phone: str, code: str, settings: Settings) -> None: ...


def _twilio_credentials(settings: Settings) -> tuple[str, str]:
    """Return HTTP Basic credentials without logging credentials or configuration."""
    if settings.twilio_api_key_sid and settings.twilio_api_key_secret:
        return settings.twilio_api_key_sid, settings.twilio_api_key_secret
    if settings.twilio_account_sid and settings.twilio_auth_token:
        return settings.twilio_account_sid, settings.twilio_auth_token
    raise OtpDeliveryError("twilio_misconfigured")


def _twilio_request(*, path: str, data: dict[str, str], settings: Settings) -> dict:
    username, password = _twilio_credentials(settings)
    auth = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    request = Request(
        f"https://verify.twilio.com/v2/{path}",
        data=urlencode(data).encode("utf-8"),
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.twilio_verify_timeout_seconds) as response:
            raw = response.read(4096)
    except HTTPError as exc:
        category = _classify_twilio_http_error(exc)
        logger.warning(
            "Citizen OTP Twilio Verify request failed category=%s status=%s",
            category,
            exc.code,
        )
        raise OtpDeliveryError(category) from exc
    except (URLError, TimeoutError) as exc:
        logger.warning("Citizen OTP Twilio Verify network failure error=%s", type(exc).__name__)
        raise OtpDeliveryError("twilio_transient") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OtpDeliveryError("twilio_malformed_response") from exc
    if not isinstance(payload, dict):
        raise OtpDeliveryError("twilio_malformed_response")
    return payload


def _classify_twilio_http_error(exc: HTTPError) -> str:
    # Verify error codes are deliberately not exposed to client responses/logs.
    if exc.code in {401, 403}:
        return "twilio_auth"
    if exc.code == 404:
        return "twilio_not_found"
    if exc.code == 429:
        return "twilio_rate_limited"
    if exc.code >= 500:
        return "twilio_transient"
    return "twilio_permanent"


def start_twilio_verify(*, canonical_phone: str, settings: Settings) -> str:
    """Start exactly one Verify SMS. Twilio generates the authoritative OTP."""
    service_sid = settings.twilio_verify_service_sid
    if not service_sid:
        raise OtpDeliveryError("twilio_misconfigured")
    payload = _twilio_request(
        path=f"Services/{service_sid}/Verifications",
        data={"To": canonical_phone, "Channel": "sms"},
        settings=settings,
    )
    if payload.get("status") != "pending" or not isinstance(payload.get("sid"), str):
        raise OtpDeliveryError("twilio_start_rejected")
    return payload["sid"]


def check_twilio_verify(*, canonical_phone: str, code: str, settings: Settings) -> bool:
    """Only an explicit Verify status=approved proves possession of the phone."""
    service_sid = settings.twilio_verify_service_sid
    if not service_sid:
        raise OtpVerificationError("twilio_misconfigured")
    try:
        payload = _twilio_request(
            path=f"Services/{service_sid}/VerificationCheck",
            data={"To": canonical_phone, "Code": code.strip()},
            settings=settings,
        )
    except OtpDeliveryError as exc:
        raise OtpVerificationError(exc.category) from exc
    return payload.get("status") == "approved"


class MockCitizenOtpDeliveryProvider:
    def deliver(self, *, canonical_phone: str, code: str, settings: Settings) -> None:
        logger.info(
            "Citizen OTP delivery skipped (channel=mock env=%s) phone=%s",
            settings.app_env,
            _mask_phone(canonical_phone),
        )
        _emit_dev_plaintext(canonical_phone, code, reason="mock_or_test", cfg=settings)


class SnsCitizenOtpDeliveryProvider:
    def deliver(self, *, canonical_phone: str, code: str, settings: Settings) -> None:
        # Sandbox fails closed: empty allowlist blocks all real SMS destinations.
        if settings.notification_sandbox:
            allowlist = set(settings.notification_allowlist_phones)
            if not allowlist or canonical_phone not in allowlist:
                logger.warning(
                    "OTP SMS blocked by notification sandbox allowlist phone=%s allowlist_empty=%s",
                    _mask_phone(canonical_phone),
                    not allowlist,
                )
                _emit_dev_plaintext(canonical_phone, code, reason="sandbox_block", cfg=settings)
                return

        client = boto3.client("sns", region_name=settings.aws_region)
        message = f"BaladiGuard verification code: {code}. It expires in 5 minutes."
        attributes: dict[str, dict[str, str]] = {
            "AWS.SNS.SMS.SMSType": {
                "DataType": "String",
                "StringValue": "Transactional",
            },
        }
        if settings.sns_sms_sender_id:
            attributes["AWS.SNS.SMS.SenderID"] = {
                "DataType": "String",
                "StringValue": settings.sns_sms_sender_id,
            }

        try:
            client.publish(
                PhoneNumber=canonical_phone,
                Message=message,
                MessageAttributes=attributes,
            )
            logger.info("Citizen OTP SMS published phone=%s", _mask_phone(canonical_phone))
            _emit_dev_plaintext(canonical_phone, code, reason="sns_published", cfg=settings)
        except (BotoCoreError, ClientError) as exc:
            logger.exception(
                "Citizen OTP SMS publish failed phone=%s", _mask_phone(canonical_phone)
            )
            if settings.app_env in {"local", "development"}:
                _emit_dev_plaintext(
                    canonical_phone, code, reason="sns_publish_failed", cfg=settings
                )
                return
            raise OtpDeliveryError("sns_publish_failed") from exc


def whatsapp_otp_uses_session_text(settings: Settings) -> bool:
    return (settings.citizen_otp_whatsapp_message_mode or "template").strip().lower() == (
        "session_text"
    )


def session_otp_text_body(code: str) -> str:
    return f"BaladiGuard verification code: {code}. It expires in 5 minutes. Do not share it."


def build_whatsapp_otp_payload(*, canonical_phone: str, code: str, settings: Settings) -> dict:
    """Build Graph send payload. Never logged; tests inspect the returned dict."""
    destination = canonical_phone[1:] if canonical_phone.startswith("+") else canonical_phone
    if whatsapp_otp_uses_session_text(settings):
        return {
            "messaging_product": "whatsapp",
            "to": destination,
            "type": "text",
            "text": {"preview_url": False, "body": session_otp_text_body(code)},
        }
    template = settings.citizen_otp_whatsapp_template_name
    language = settings.citizen_otp_whatsapp_template_language or "en"
    components: list[dict] = [
        {
            "type": "body",
            "parameters": [{"type": "text", "text": code}],
        }
    ]
    if settings.citizen_otp_whatsapp_template_button_index is not None:
        components.append(
            {
                "type": "button",
                "sub_type": "url",
                "index": str(settings.citizen_otp_whatsapp_template_button_index),
                "parameters": [{"type": "text", "text": code}],
            }
        )
    return {
        "messaging_product": "whatsapp",
        "to": destination,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": language},
            "components": components,
        },
    }


class WhatsAppCitizenOtpDeliveryProvider:
    """Meta Cloud API OTP delivery (auth template, or sandbox session text)."""

    def deliver(self, *, canonical_phone: str, code: str, settings: Settings) -> None:
        if settings.notification_sandbox:
            allowlist = set(settings.notification_allowlist_phones)
            if not allowlist or canonical_phone not in allowlist:
                logger.warning(
                    "OTP WhatsApp blocked by notification sandbox allowlist phone=%s "
                    "allowlist_empty=%s",
                    _mask_phone(canonical_phone),
                    not allowlist,
                )
                raise OtpDeliveryError("sandbox_blocked")

        session_text = whatsapp_otp_uses_session_text(settings)
        if session_text:
            if settings.app_env == "production" or not settings.notification_sandbox:
                raise OtpDeliveryError("whatsapp_session_text_forbidden")

        token = settings.citizen_otp_whatsapp_access_token
        phone_number_id = settings.citizen_otp_whatsapp_phone_number_id
        template = settings.citizen_otp_whatsapp_template_name
        version = settings.citizen_otp_whatsapp_graph_api_version or "v21.0"
        if not token or not phone_number_id:
            raise OtpDeliveryError("whatsapp_misconfigured")
        if not session_text and not template:
            raise OtpDeliveryError("whatsapp_misconfigured")

        url = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"
        payload = build_whatsapp_otp_payload(
            canonical_phone=canonical_phone, code=code, settings=settings
        )
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=settings.citizen_otp_whatsapp_timeout_seconds) as resp:
                # Read body for transport completeness; never log it (may echo OTP params).
                resp.read(4096)
        except HTTPError as exc:
            category = _classify_whatsapp_http_error(exc)
            logger.warning(
                "Citizen OTP WhatsApp delivery failed category=%s status=%s phone=%s",
                category,
                exc.code,
                _mask_phone(canonical_phone),
            )
            raise OtpDeliveryError(category) from exc
        except (URLError, TimeoutError) as exc:
            logger.warning(
                "Citizen OTP WhatsApp delivery timeout/network phone=%s error=%s",
                _mask_phone(canonical_phone),
                type(exc).__name__,
            )
            raise OtpDeliveryError("whatsapp_transient") from exc

        logger.info("Citizen OTP WhatsApp published phone=%s", _mask_phone(canonical_phone))
        _emit_dev_plaintext(canonical_phone, code, reason="whatsapp_published", cfg=settings)


def _classify_whatsapp_http_error(exc: HTTPError) -> str:
    graph_code = _whatsapp_graph_error_code(exc)
    if graph_code == 131047:
        return "whatsapp_session_window_closed"
    if graph_code == 131030:
        return "whatsapp_not_in_allowed_list"
    status = exc.code
    if status in {401, 403}:
        return "whatsapp_auth"
    if status == 404:
        return "whatsapp_template"
    if status == 429:
        return "whatsapp_throttled"
    if status >= 500:
        return "whatsapp_transient"
    return "whatsapp_permanent"


def _whatsapp_graph_error_code(exc: HTTPError) -> int | None:
    try:
        raw = exc.read(4096)
    except Exception:
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    try:
        return int(code)
    except (TypeError, ValueError):
        return None


def build_citizen_otp_delivery_provider(
    channel: OtpDeliveryChannel,
) -> CitizenOtpDeliveryProvider:
    if channel == "sns":
        return SnsCitizenOtpDeliveryProvider()
    if channel == "whatsapp":
        return WhatsAppCitizenOtpDeliveryProvider()
    return MockCitizenOtpDeliveryProvider()


def deliver_citizen_otp(
    *,
    phone: str,
    region: str | None,
    code: str | None,
    settings: Settings | None = None,
) -> PublicOtpDeliveryChannel:
    """Deliver a one-time code. Never includes the code in HTTP responses or logs.

    Returns a public channel label for adaptable mobile/web copy (``sms`` /
    ``whatsapp`` / ``dev``). Does not reveal account existence.
    """
    cfg = settings or get_settings()
    try:
        canonical = normalize_phone(phone, region)
    except PhoneNormalizationError:
        canonical = phone.strip()

    channel = resolve_citizen_otp_delivery_channel(cfg)
    public = public_otp_delivery_channel(channel)
    if channel == "twilio":
        # This intentionally does not call a local transport provider: Verify
        # creates and later checks the one authoritative code.
        start_twilio_verify(canonical_phone=canonical, settings=cfg)
        emit_metric("CitizenOtpDelivery", dimensions={"channel": channel, "result": "success"})
        return public
    if code is None:
        raise OtpDeliveryError("local_otp_missing")
    provider = build_citizen_otp_delivery_provider(channel)

    started = __import__("time").perf_counter()
    try:
        provider.deliver(canonical_phone=canonical, code=code, settings=cfg)
        emit_metric(
            "CitizenOtpDelivery",
            dimensions={"channel": channel, "result": "success"},
        )
    except Exception as exc:
        category = getattr(exc, "category", type(exc).__name__)
        emit_metric(
            "CitizenOtpDelivery",
            dimensions={"channel": channel, "result": "failure", "category": str(category)[:40]},
        )
        raise
    finally:
        emit_metric(
            "CitizenOtpDeliveryLatency",
            value=(__import__("time").perf_counter() - started) * 1000.0,
            unit="Milliseconds",
            dimensions={"channel": channel},
        )
    return public
