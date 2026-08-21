"""WhatsApp channel orchestration service (issue #296)."""

from __future__ import annotations

import logging

from app.config import get_settings
from app.core.metrics import emit_metric
from app.database.store_factory import get_whatsapp_conversation_store, get_whatsapp_dedup_store
from app.services.whatsapp.fsm import WhatsAppFlowEngine
from app.services.whatsapp.graph import build_whatsapp_graph_client
from app.services.whatsapp.webhook_parse import parse_webhook_payload

logger = logging.getLogger(__name__)


class WhatsAppIngestionService:
    def process_webhook_payload(self, payload: dict) -> dict[str, int]:
        settings = get_settings()
        if not settings.whatsapp_enabled:
            emit_metric("WhatsAppWebhookRejected", dimensions={"reason": "disabled"})
            return {"accepted": 0, "duplicates": 0, "ignored": 0}

        events = parse_webhook_payload(payload)
        dedup = get_whatsapp_dedup_store()
        engine = WhatsAppFlowEngine(
            conversation_store=get_whatsapp_conversation_store(),
            graph=build_whatsapp_graph_client(settings),
            settings=settings,
        )

        accepted = 0
        duplicates = 0
        ignored = 0
        failed = 0
        for event in events:
            if event.kind == "status":
                ignored += 1
                continue
            if not event.message_id:
                ignored += 1
                continue
            is_new = dedup.try_record(
                message_id=event.message_id,
                ttl_seconds=settings.whatsapp_dedup_ttl_seconds,
            )
            if not is_new:
                duplicates += 1
                emit_metric("WhatsAppDuplicateMessage", dimensions={"kind": event.kind})
                continue
            try:
                engine.handle_event(event)
                accepted += 1
                emit_metric("WhatsAppMessageAccepted", dimensions={"kind": event.kind})
            except Exception as exc:  # noqa: BLE001
                try:
                    dedup.release(message_id=event.message_id)
                except Exception:
                    logger.warning(
                        "WhatsApp dedup release failed kind=%s",
                        event.kind,
                    )
                failed += 1
                logger.warning(
                    "WhatsApp event processing failed kind=%s error=%s",
                    event.kind,
                    type(exc).__name__,
                )
                emit_metric("WhatsAppProcessingFailure", dimensions={"kind": event.kind})
        return {
            "accepted": accepted,
            "duplicates": duplicates,
            "ignored": ignored,
            "failed": failed,
        }


whatsapp_ingestion_service = WhatsAppIngestionService()
