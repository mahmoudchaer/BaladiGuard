"""Low-cardinality metric events for CloudWatch filters / EMF (issue #185).

EMF CloudWatch series use a **stable** dimension set of ``env`` only so alarms
and dashboards can select the same time series across deploys. High-cardinality
context (path, version, outcome, …) stays on ``metric_event`` log lines.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Any

from app.core.job_context import get_job_id
from app.core.request_context import get_request_id

logger = logging.getLogger("app.metrics")

NAMESPACE = "BaladiGuard"
# Alarm/dashboard selector — must match infra/observability/*.json + apply script.
STABLE_EMF_DIMENSION_KEYS = ("env",)

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_TICKET_ID_RE = re.compile(r"\btkt_[0-9a-fA-F]+\b")
_CHALLENGE_ID_RE = re.compile(r"\bchl_[0-9a-fA-F]+\b")
_TICKET_NUMBER_RE = re.compile(r"\bBG-\d{4}-\d+\b")
_HEX_ID_RE = re.compile(r"\b[0-9a-fA-F]{16,}\b")

_METRIC_BUFFER_MAX = 2000
_metric_lock = Lock()
_metric_buffer: deque[MetricSample] = deque(maxlen=_METRIC_BUFFER_MAX)


@dataclass(frozen=True, slots=True)
class MetricSample:
    name: str
    value: float
    unit: str
    dimensions: dict[str, str]
    timestamp: float
    request_id: str | None
    job_id: str | None


def record_metric_sample(sample: MetricSample) -> None:
    with _metric_lock:
        _metric_buffer.append(sample)


def recent_metric_samples(
    *,
    since: float | None = None,
    name: str | None = None,
) -> list[MetricSample]:
    with _metric_lock:
        items = list(_metric_buffer)
    if since is not None:
        items = [item for item in items if item.timestamp >= since]
    if name is not None:
        items = [item for item in items if item.name == name]
    return items


def clear_metric_samples() -> None:
    with _metric_lock:
        _metric_buffer.clear()


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


def stable_emf_dimensions(*, env: str | None = None) -> dict[str, str]:
    """Return the dimension map published into CloudWatch EMF / alarm selectors."""
    return {"env": (env or _app_env())}


def build_emf_record(
    name: str,
    *,
    value: float,
    unit: str,
    env: str | None = None,
    timestamp_ms: int | None = None,
) -> dict[str, Any]:
    """Build the EMF JSON object that CloudWatch agents parse from stdout."""
    emf_dims = stable_emf_dimensions(env=env)
    return {
        "_aws": {
            "Timestamp": int(timestamp_ms if timestamp_ms is not None else time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": NAMESPACE,
                    "Dimensions": [list(STABLE_EMF_DIMENSION_KEYS)],
                    "Metrics": [{"Name": name, "Unit": unit}],
                }
            ],
        },
        name: value,
        **emf_dims,
    }


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
    # Version stays in logs for triage; it is intentionally excluded from EMF
    # identity so alarms do not need per-deploy selector updates.
    dims.setdefault("version", _app_version())
    request_id = get_request_id()
    job_id = get_job_id()
    dim_text = " ".join(f"{key}={dim_value}" for key, dim_value in sorted(dims.items()))
    suffix = ""
    if request_id:
        suffix += f" request_id={request_id}"
    if job_id:
        suffix += f" job_id={job_id}"
    record_metric_sample(
        MetricSample(
            name=name,
            value=float(value),
            unit=unit,
            dimensions=dims,
            timestamp=time.time(),
            request_id=request_id,
            job_id=job_id,
        )
    )
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
    emf = build_emf_record(name, value=value, unit=unit, env=dims["env"])
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
