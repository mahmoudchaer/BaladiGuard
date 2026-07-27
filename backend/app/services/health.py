"""Runtime health checks for the BaladiGuard API."""

from __future__ import annotations

import logging
import os
from typing import Any

from app.config import get_settings
from app.database.dynamodb_tables import build_table_name
from app.database.store_factory import get_ticket_store

logger = logging.getLogger(__name__)


def _app_env() -> str:
    return os.getenv("APP_ENV", "").strip() or os.getenv("ENVIRONMENT", "").strip() or "local"


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
        return {
            "backend": backend,
            "status": "error",
            "detail": type(exc).__name__,
        }


def build_health_payload() -> dict[str, Any]:
    database = check_database()
    overall = "ok" if database.get("status") == "ok" else "degraded"
    return {
        "status": overall,
        "service": "baladiguard-api",
        "env": _app_env(),
        "database": database,
    }
