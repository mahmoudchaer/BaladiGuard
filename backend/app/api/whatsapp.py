"""WhatsApp Cloud API webhook endpoints (issue #296)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import get_settings
from app.core.metrics import emit_metric
from app.services.whatsapp.service import whatsapp_ingestion_service
from app.services.whatsapp.signature import verify_meta_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/whatsapp", tags=["whatsapp"])


@router.get("/webhook")
def verify_whatsapp_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> Response:
    settings = get_settings()
    if not settings.whatsapp_enabled:
        return JSONResponse(status_code=503, content={"detail": "WhatsApp channel disabled."})
    if (
        hub_mode == "subscribe"
        and hub_verify_token
        and settings.whatsapp_verify_token
        and hub_verify_token == settings.whatsapp_verify_token
        and hub_challenge is not None
    ):
        emit_metric("WhatsAppWebhookVerified")
        return PlainTextResponse(content=hub_challenge, status_code=200)
    emit_metric("WhatsAppWebhookVerifyRejected")
    return JSONResponse(status_code=403, content={"detail": "Webhook verification failed."})


@router.post("/webhook")
async def receive_whatsapp_webhook(request: Request) -> Response:
    settings = get_settings()
    if not settings.whatsapp_enabled:
        return JSONResponse(status_code=503, content={"detail": "WhatsApp channel disabled."})

    raw_body = await request.body()
    # Bound payload size before parsing.
    if len(raw_body) > settings.whatsapp_max_webhook_bytes:
        emit_metric("WhatsAppWebhookRejected", dimensions={"reason": "oversized"})
        return JSONResponse(status_code=413, content={"detail": "Payload too large."})

    signature = request.headers.get("X-Hub-Signature-256")
    app_secret = settings.whatsapp_app_secret or ""
    if not verify_meta_signature(
        app_secret=app_secret,
        raw_body=raw_body,
        signature_header=signature,
    ):
        emit_metric("WhatsAppWebhookRejected", dimensions={"reason": "bad_signature"})
        logger.warning("WhatsApp webhook rejected invalid signature")
        return JSONResponse(status_code=403, content={"detail": "Invalid signature."})

    try:
        payload = await request.json()
    except Exception:
        emit_metric("WhatsAppWebhookRejected", dimensions={"reason": "malformed"})
        return JSONResponse(status_code=400, content={"detail": "Malformed JSON."})
    if not isinstance(payload, dict):
        return JSONResponse(status_code=400, content={"detail": "Malformed JSON object."})

    # Acknowledge quickly; process synchronously for mock/local and small loads.
    # Production may move heavy media/submit work to a worker later.
    result = whatsapp_ingestion_service.process_webhook_payload(payload)
    return JSONResponse(status_code=200, content={"ok": True, **result})
