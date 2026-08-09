"""Background readiness metric publisher (issue #185).

Docker HEALTHCHECK / kube liveness use ``/health/live`` and must not depend on
DynamoDB. Readiness alarms need a continuous ``ReadyProbeSuccess`` series, so
each API process publishes the probe on a fixed interval. Load balancers may
still poll ``/health/ready``; this loop is the guaranteed producer.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None


def readiness_probe_interval_seconds() -> float:
    raw = os.getenv("READINESS_PROBE_INTERVAL_SECONDS", "30").strip() or "30"
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 30.0


def publish_ready_probe_once(
    build_readiness: Callable[[], tuple[dict, bool]] | None = None,
) -> bool:
    """Run one readiness evaluation and emit ``ReadyProbeSuccess``."""
    if build_readiness is None:
        from app.services.health import build_readiness_payload

        build_readiness = build_readiness_payload
    _payload, ready = build_readiness()
    return ready


def _loop() -> None:
    interval = readiness_probe_interval_seconds()
    logger.info("Readiness probe publisher started interval_seconds=%s", interval)
    while not _stop.wait(interval):
        try:
            publish_ready_probe_once()
        except Exception:
            logger.exception("Readiness probe publisher iteration failed")


def start_readiness_probe_publisher() -> None:
    """Start the daemon publisher once per process."""
    global _thread
    if os.getenv("READINESS_PROBE_PUBLISHER", "true").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        logger.info("Readiness probe publisher disabled via READINESS_PROBE_PUBLISHER")
        return
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    # Publish immediately so the first minute is not empty after deploy.
    try:
        publish_ready_probe_once()
    except Exception:
        logger.exception("Initial readiness probe publish failed")
    _thread = threading.Thread(target=_loop, name="readiness-probe-publisher", daemon=True)
    _thread.start()


def stop_readiness_probe_publisher() -> None:
    """Signal the publisher to stop (tests / graceful shutdown)."""
    _stop.set()
