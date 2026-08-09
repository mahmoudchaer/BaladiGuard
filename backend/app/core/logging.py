"""Application logging setup for local demos and deployed environments.

Production should set ``LOG_FORMAT=json`` so CloudWatch / log aggregators can
parse request IDs, env, and version. Sensitive field names and values are
redacted from structured extras, rendered messages, and exception text
(issue #185).
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

from app.core.request_context import get_request_id

# Mapping-key redaction includes authorization headers stored as structured fields.
_SENSITIVE_KEY = (
    r"password|passwd|secret|token|authorization|api[_-]?key|reset[_-]?code|"
    r"otp|credential|access[_-]?token|refresh[_-]?token|session"
)
_SENSITIVE_KEY_RE = re.compile(rf"({_SENSITIVE_KEY})", re.IGNORECASE)

# Free-text assignments exclude ``authorization`` so auth-scheme redaction below
# is not collapsed to ``Authorization=[REDACTED]`` after Bearer/Basic handling.
_SENSITIVE_ASSIGN_KEY = (
    r"password|passwd|secret|token|api[_-]?key|reset[_-]?code|"
    r"otp|credential|access[_-]?token|refresh[_-]?token|session"
)

# Bearer/Basic: single credential token. Digest: full parameter list (may include spaces).
_AUTH_BEARER_BASIC_RE = re.compile(r"(?i)\b(authorization\s*[:=]\s*)?(bearer|basic)\s+(\S+)")
_AUTH_DIGEST_RE = re.compile(r"(?i)\b(authorization\s*[:=]\s*)?(digest)\s+([^\n]+)")

# key="quoted value" / key='quoted value'
_QUOTED_ASSIGN_RE = re.compile(
    rf"(?i)\b({_SENSITIVE_ASSIGN_KEY})\b\s*[:=]\s*"
    rf"(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')"
)

# key=unquoted value that may contain spaces — consume through end of line or
# the next structured delimiter (comma/semicolon), not the first whitespace.
_UNQUOTED_ASSIGN_RE = re.compile(rf"(?i)\b({_SENSITIVE_ASSIGN_KEY})\b\s*[:=]\s*([^\n,;]+)")

_REDACTED = "[REDACTED]"


def _app_version() -> str:
    return os.getenv("APP_VERSION", "0.1.0").strip() or "0.1.0"


def _app_env() -> str:
    return (
        os.getenv("APP_ENV", "").strip() or os.getenv("ENVIRONMENT", "").strip() or "local"
    ).lower()


def redact_text(text: str) -> str:
    """Mask sensitive assignments and auth credentials inside free-form text."""
    if not text:
        return text

    def _auth_repl(match: re.Match[str]) -> str:
        prefix = match.group(1) or ""
        scheme = match.group(2)
        return f"{prefix}{scheme} {_REDACTED}"

    # Digest first so its comma-separated params are not truncated to one token.
    scrubbed = _AUTH_DIGEST_RE.sub(_auth_repl, text)
    scrubbed = _AUTH_BEARER_BASIC_RE.sub(_auth_repl, scrubbed)
    scrubbed = _QUOTED_ASSIGN_RE.sub(lambda match: f"{match.group(1)}={_REDACTED}", scrubbed)
    scrubbed = _UNQUOTED_ASSIGN_RE.sub(lambda match: f"{match.group(1)}={_REDACTED}", scrubbed)
    return scrubbed


def redact_value(value: Any) -> Any:
    """Recursively redact sensitive keys in mappings and values in sequences."""
    if isinstance(value, dict):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        # Treat 2-tuples as potential (key, value) pairs from structured extras.
        if len(value) == 2 and isinstance(value[0], str) and _SENSITIVE_KEY_RE.search(value[0]):
            return (value[0], _REDACTED)
        return tuple(redact_value(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_mapping(values: dict[str, Any]) -> dict[str, Any]:
    """Return a deep-ish copy with sensitive keys/values replaced by ``[REDACTED]``."""
    redacted: dict[str, Any] = {}
    for key, value in values.items():
        if _SENSITIVE_KEY_RE.search(str(key)):
            redacted[key] = _REDACTED
        else:
            redacted[key] = redact_value(value)
    return redacted


def safe_exception_payload(exc_info: tuple[Any, Any, Any]) -> dict[str, str]:
    """Allowlisted exception metadata with redacted message (no raw traceback dump)."""
    exc_type, exc, _tb = exc_info
    type_name = getattr(exc_type, "__name__", type(exc_type).__name__)
    return {
        "type": type_name,
        "message": redact_text(str(exc) if exc is not None else ""),
    }


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line for centralized log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        try:
            raw_message = record.getMessage()
        except Exception:
            raw_message = str(record.msg)
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(raw_message),
            "service": "baladiguard-api",
            "env": _app_env(),
            "version": _app_version(),
        }
        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            # Prefer allowlisted structured fields; keep a redacted traceback for
            # operators without shipping raw secret-bearing exception text.
            payload["exception"] = safe_exception_payload(record.exc_info)
            payload["exception_traceback"] = redact_text(self.formatException(record.exc_info))
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
