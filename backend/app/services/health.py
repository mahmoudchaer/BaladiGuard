"""Runtime health checks for the BaladiGuard API (issue #185)."""

from __future__ import annotations

import logging
import os
from typing import Any

from app.config import get_settings
from app.core.config_validation import resolve_app_env, validate_configuration
from app.core.metrics import emit_metric
from app.database.dynamodb_tables import build_table_name
from app.database.store_factory import get_ticket_store

logger = logging.getLogger(__name__)

# Pending+processing above this is a local queue-health signal (memory backend).
AI_QUEUE_BACKLOG_WARN = 25


def app_version() -> str:
    return os.getenv("APP_VERSION", "0.1.0").strip() or "0.1.0"


def check_database() -> dict[str, Any]:
    """Optionally verify ticket-store connectivity based on configured backend."""
    settings = get_settings()
    backend = "dynamodb" if settings.use_dynamodb else "memory"
    try:
        if not settings.use_dynamodb:
            # Touch the in-memory store so health still exercises the store path.
            store = get_ticket_store()
            store.list()
            return {"backend": "memory", "status": "ok"}

        from app.database.dynamodb import create_dynamodb_resource

        resource = create_dynamodb_resource(settings)
        table_name = build_table_name(settings.dynamodb_table_prefix, "tickets")
        table = resource.Table(table_name)
        # Load table metadata; raises if the table/credentials/network are unusable.
        _ = table.table_status
        return {"backend": "dynamodb", "status": "ok", "table": table_name}
    except Exception as exc:
        logger.error(
            "Health database check failed (%s): %s",
            type(exc).__name__,
            exc,
        )
        emit_metric(
            "DynamoDbErrors",
            dimensions={"operation": "health_check", "backend": backend},
        )
        return {
            "backend": backend,
            "status": "error",
            "detail": type(exc).__name__,
        }


def check_configuration() -> dict[str, Any]:
    """Report configuration readiness without exposing secret values."""
    result = validate_configuration()
    if not result.ok:
        for issue in result.issues:
            logger.error(
                "Configuration issue code=%s severity=%s message=%s",
                issue.code,
                issue.severity,
                issue.message,
            )
    return result.to_health_dict()


def check_ai_queue() -> dict[str, Any]:
    """Summarize AI queue health without scanning DynamoDB on every probe.

    Memory/local backends enumerate the in-process store. DynamoDB deployments
    publish ``AiQueuePending`` / ``AiQueueFailed`` from AI workers and startup
    recovery instead of a health-time table scan.
    """
    settings = get_settings()
    if settings.use_dynamodb:
        return {
            "status": "metrics",
            "source": "worker_metrics",
            "backlogWarnThreshold": AI_QUEUE_BACKLOG_WARN,
        }

    pending = 0
    processing = 0
    failed = 0
    try:
        for ticket in get_ticket_store().list():
            status = ticket.ai_processing_status
            if status == "pending":
                pending += 1
            elif status == "processing":
                processing += 1
            elif status == "failed":
                failed += 1
    except Exception as exc:
        logger.error(
            "Health AI queue check failed (%s): %s",
            type(exc).__name__,
            exc,
        )
        return {
            "status": "error",
            "detail": type(exc).__name__,
            "pending": 0,
            "processing": 0,
            "failed": 0,
            "source": "memory_store",
        }

    backlog = pending + processing
    status = "ok" if backlog <= AI_QUEUE_BACKLOG_WARN else "backlogged"
    emit_metric("AiQueuePending", value=float(pending), unit="Count")
    emit_metric("AiQueueProcessing", value=float(processing), unit="Count")
    emit_metric("AiQueueFailed", value=float(failed), unit="Count")
    return {
        "status": status,
        "pending": pending,
        "processing": processing,
        "failed": failed,
        "source": "memory_store",
        "backlogWarnThreshold": AI_QUEUE_BACKLOG_WARN,
    }


def build_liveness_payload() -> dict[str, Any]:
    """Process-up signal only — never depends on DynamoDB/S3/config."""
    return {
        "status": "live",
        "service": "baladiguard-api",
        "env": resolve_app_env(),
        "version": app_version(),
    }


def build_readiness_payload() -> tuple[dict[str, Any], bool]:
    """Dependency readiness for load balancers / deploy gates.

    Returns ``(payload, ready)``. Ready requires database + configuration OK.
    AI queue depth is reported for operators but does not fail readiness (queue
    backlog pages via metric alarms instead of taking the service out of rotation).
    """
    database = check_database()
    configuration = check_configuration()
    ai = check_ai_queue()
    ready = database.get("status") == "ok" and configuration.get("status") == "ok"
    payload = {
        "status": "ready" if ready else "not_ready",
        "service": "baladiguard-api",
        "env": resolve_app_env(),
        "version": app_version(),
        "database": database,
        "config": configuration,
        "ai": ai,
    }
    emit_metric(
        "ReadyProbeSuccess",
        value=1.0 if ready else 0.0,
        unit="None",
    )
    return payload, ready


def build_health_payload() -> dict[str, Any]:
    """Human/composite health: always safe for basic probes that expect HTTP 200."""
    database = check_database()
    configuration = check_configuration()
    ai = check_ai_queue()
    overall = (
        "ok"
        if database.get("status") == "ok" and configuration.get("status") == "ok"
        else "degraded"
    )
    return {
        "status": overall,
        "service": "baladiguard-api",
        "env": resolve_app_env(),
        "version": app_version(),
        "database": database,
        "config": configuration,
        "ai": ai,
        "probes": {
            "liveness": "/health/live",
            "readiness": "/health/ready",
            "composite": "/health",
        },
    }
