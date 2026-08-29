"""WhatsApp Graph API client Protocol + mock/cloud implementations (issue #296)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from io import BytesIO
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutboundTextMessage:
    to_wa_id: str
    body: str
    phone_number_id: str


@dataclass
class MockWhatsAppGraphClient:
    """In-memory Graph stand-in for local/tests. No real Meta calls."""

    sent: list[OutboundTextMessage] = field(default_factory=list)
    media_bytes: dict[str, tuple[bytes, str]] = field(default_factory=dict)

    def send_text(self, *, phone_number_id: str, to_wa_id: str, body: str) -> str:
        self.sent.append(
            OutboundTextMessage(to_wa_id=to_wa_id, body=body, phone_number_id=phone_number_id)
        )
        return f"mock_out_{len(self.sent)}"

    def download_media(self, *, media_id: str) -> tuple[bytes, str]:
        if media_id in self.media_bytes:
            return self.media_bytes[media_id]
        # Deterministic tiny JPEG for tests when media_id is unknown.
        buffer = BytesIO()
        Image.new("RGB", (32, 32), color=(40, 120, 200)).save(buffer, format="JPEG")
        return buffer.getvalue(), "image/jpeg"


class WhatsAppGraphClient(Protocol):
    def send_text(self, *, phone_number_id: str, to_wa_id: str, body: str) -> str: ...

    def download_media(self, *, media_id: str) -> tuple[bytes, str]: ...


class CloudWhatsAppGraphClient:
    """Real Meta Graph API client. Used when WHATSAPP_PROVIDER=cloud."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def send_text(self, *, phone_number_id: str, to_wa_id: str, body: str) -> str:
        token = self._settings.whatsapp_access_token
        version = self._settings.whatsapp_graph_api_version
        if not token:
            raise RuntimeError("WHATSAPP_ACCESS_TOKEN is not configured.")
        url = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to_wa_id,
            "type": "text",
            "text": {"body": body[:4096]},
        }
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
            with urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("WhatsApp Graph send_text failed error=%s", type(exc).__name__)
            raise RuntimeError("WhatsApp outbound send failed.") from exc
        messages = data.get("messages") or []
        if messages and isinstance(messages[0], dict) and messages[0].get("id"):
            return str(messages[0]["id"])
        return "cloud_send_ok"

    def download_media(self, *, media_id: str) -> tuple[bytes, str]:
        token = self._settings.whatsapp_access_token
        version = self._settings.whatsapp_graph_api_version
        if not token:
            raise RuntimeError("WHATSAPP_ACCESS_TOKEN is not configured.")
        meta_url = f"https://graph.facebook.com/{version}/{media_id}"
        meta_req = Request(meta_url, headers={"Authorization": f"Bearer {token}"}, method="GET")
        try:
            with urlopen(meta_req, timeout=20) as response:
                meta = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("WhatsApp media metadata fetch failed.") from exc
        download_url = meta.get("url")
        if not isinstance(download_url, str):
            raise RuntimeError("WhatsApp media URL is missing.")
        allowed = (
            download_url.startswith("https://lookaside.fbsbx.com/")
            or download_url.startswith("https://graph.facebook.com/")
            or "fbcdn.net" in download_url
        )
        if not allowed:
            raise RuntimeError("WhatsApp media URL is not an approved provider destination.")
        media_req = Request(
            download_url, headers={"Authorization": f"Bearer {token}"}, method="GET"
        )
        try:
            with urlopen(media_req, timeout=30) as response:
                content_type = response.headers.get("Content-Type") or "application/octet-stream"
                body = response.read(5 * 1024 * 1024 + 1)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError("WhatsApp media download failed.") from exc
        if len(body) > 5 * 1024 * 1024:
            raise RuntimeError("WhatsApp media exceeds 5MB limit.")
        return body, content_type.split(";")[0].strip()


_mock_singleton: MockWhatsAppGraphClient | None = None


def get_mock_graph_client() -> MockWhatsAppGraphClient:
    global _mock_singleton
    if _mock_singleton is None:
        _mock_singleton = MockWhatsAppGraphClient()
    return _mock_singleton


def reset_mock_graph_client() -> None:
    global _mock_singleton
    _mock_singleton = MockWhatsAppGraphClient()


def build_whatsapp_graph_client(settings: Settings | None = None) -> WhatsAppGraphClient:
    cfg = settings or get_settings()
    provider = (cfg.whatsapp_provider or "mock").strip().lower()
    if provider == "cloud":
        return CloudWhatsAppGraphClient(cfg)
    return get_mock_graph_client()
