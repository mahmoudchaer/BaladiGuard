"""Low-cardinality metric events for CloudWatch filters / EMF (issue #185)."""

from __future__ import annotations

import json
import logging
import os
import re
import time

from app.core.request_context import get_request_id

logger = logging.getLogger("app.metrics")

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_TICKET_ID_RE = re.compile(r"\btkt_[0-9a-fA-F]+\b")
_CHALLENGE_ID_RE = re.compile(r"\bchl_[0-9a-fA-F]+\b")
_TICKET_NUMBER_RE = re.compile(r"\bBG-\d{4}-\d+\b")
_HEX_ID_RE = re.compile(r"\b[0-9a-fA-F]{16,}\b")


def _app_version() -> str:
    return os.getenv("APP_VERSION", "0.1.0").strip() or "0.1.0"


def _app_env() -> str:
    return (
        os.getenv("APP_ENV", "").strip() or os.getenv("ENVIRONMENT", "").strip() or "local"
    ).lower()


def metrics_emf_enabled() -> bool:
    raw = os.getenv("METRICS_EMF", "").strip().lower()
    if raw in {"true", "false"}:
        return raw == "true"
    return _app_env() == "production"


def normalize_path_group(path: str) -> str:
    """Collapse high-cardinality path segments for metric dimensions."""
    cleaned = (path or "/").split("?", 1)[0]
    cleaned = _UUID_RE.sub(":id", cleaned)
    cleaned = _TICKET_ID_RE.sub(":ticketId", cleaned)
    cleaned = _CHALLENGE_ID_RE.sub(":challengeId", cleaned)
    cleaned = _TICKET_NUMBER_RE.sub(":ticketNumber", cleaned)
    cleaned = _HEX_ID_RE.sub(":id", cleaned)
    parts = [part if not part.isdigit() else ":id" for part in cleaned.split("/")]
    grouped = "/".join(parts) or "/"
    if len(grouped) > 120:
        return grouped[:120]
    return grouped


# Keep EMF cardinality bounded. High-cardinality keys stay in metric_event logs only.
_EMF_DIMENSION_KEYS = frozenset(
    {
        "env",
        "version",
        "method",
        "status_class",
        "kind",
        "policy",
        "operation",
        "outcome",
        "event",
        "category",
        "source",
        "backend",
        "error",
        "code",
    }
)


def emit_metric(
    name: str,
    *,
    value: float = 1.0,
    unit: str = "Count",
    dimensions: dict[str, str] | None = None,
) -> None:
    """Emit a filter-friendly metric log line and optional CloudWatch EMF record."""
    dims = {key: str(dim_value)[:64] for key, dim_value in (dimensions or {}).items()}
    dims.setdefault("env", _app_env())
    dims.setdefault("version", _app_version())
    request_id = get_request_id()
    dim_text = " ".join(f"{key}={dim_value}" for key, dim_value in sorted(dims.items()))
    suffix = f" request_id={request_id}" if request_id else ""
    logger.info(
        "metric_event name=%s value=%s unit=%s %s%s",
        name,
        value,
        unit,
        dim_text,
        suffix,
    )
    if not metrics_emf_enabled():
        return
    emf_dims = {key: value for key, value in dims.items() if key in _EMF_DIMENSION_KEYS}
    if not emf_dims:
        emf_dims = {"env": dims["env"], "version": dims["version"]}
    emf = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": "BaladiGuard",
                    "Dimensions": [sorted(emf_dims.keys())],
                    "Metrics": [{"Name": name, "Unit": unit}],
                }
            ],
        },
        name: value,
        **emf_dims,
    }
    # EMF must be a single JSON object on stdout for the CloudWatch agent.
    print(json.dumps(emf, default=str, ensure_ascii=True), flush=True)


def timed_metric(
    name: str,
    *,
    dimensions: dict[str, str] | None = None,
    started_at: float | None = None,
) -> None:
    """Emit a milliseconds duration metric from ``started_at`` (perf_counter)."""
    start = started_at if started_at is not None else time.perf_counter()
    duration_ms = max(0.0, (time.perf_counter() - start) * 1000.0)
    emit_metric(name, value=round(duration_ms, 2), unit="Milliseconds", dimensions=dimensions)
