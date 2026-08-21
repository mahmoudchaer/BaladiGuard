"""HMAC signature verification for Meta WhatsApp Cloud API webhooks."""

from __future__ import annotations

import hashlib
import hmac


def verify_meta_signature(
    *, app_secret: str, raw_body: bytes, signature_header: str | None
) -> bool:
    """Validate ``X-Hub-Signature-256: sha256=<hex>`` against the raw body."""
    if not app_secret or not signature_header:
        return False
    header = signature_header.strip()
    if not header.lower().startswith("sha256="):
        return False
    provided = header.split("=", 1)[1].strip().lower()
    if not provided or any(ch not in "0123456789abcdef" for ch in provided):
        return False
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, provided)


def sign_meta_payload(*, app_secret: str, raw_body: bytes) -> str:
    """Test helper: build a valid signature header for fixture webhooks."""
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"
