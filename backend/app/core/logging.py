"""Application logging setup for local demos and deployed environments.

Production should set ``LOG_FORMAT=json`` so CloudWatch / log aggregators can
parse request IDs, env, and version. Sensitive field names are redacted from
structured extras (issue #185).
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

from app.core.request_context import get_request_id

_SENSITIVE_KEY_RE = re.compile(
    r"(password|passwd|secret|token|authorization|api[_-]?key|reset[_-]?code|"
    r"otp|credential|access[_-]?token|refresh[_-]?token|session)",
    re.IGNORECASE,
)


def _app_version() -> str:
    return os.getenv("APP_VERSION", "0.1.0").strip() or "0.1.0"


def _app_env() -> str:
    return (
        os.getenv("APP_ENV", "").strip() or os.getenv("ENVIRONMENT", "").strip() or "local"
    ).lower()


def redact_mapping(values: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy with sensitive keys replaced by ``[REDACTED]``."""
    redacted: dict[str, Any] = {}
    for key, value in values.items():
        if _SENSITIVE_KEY_RE.search(str(key)):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = redact_mapping(value)
        else:
            redacted[key] = value
    return redacted


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line for centralized log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "baladiguard-api",
            "env": _app_env(),
            "version": _app_version(),
        }
        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key
            not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "asctime",
            }
        }
        if extras:
            payload["extra"] = redact_mapping(extras)
        return json.dumps(payload, default=str, ensure_ascii=True)


def configure_logging() -> None:
    """Configure root logging once for the backend process."""
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    level = getattr(logging, level_name, logging.INFO)
    log_format = os.getenv("LOG_FORMAT", "text").strip().lower() or "text"
    if log_format not in {"text", "json"}:
        log_format = "text"

    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return

    handler = logging.StreamHandler()
    if log_format == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
