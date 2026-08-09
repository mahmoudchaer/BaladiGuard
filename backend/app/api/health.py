from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.health import (
    build_health_payload,
    build_liveness_payload,
    build_readiness_payload,
)

router = APIRouter(tags=["health"])


@router.get("/health/live")
def liveness_check() -> JSONResponse:
    """Liveness: process is up. Never depends on DynamoDB, S3, or config."""
    return JSONResponse(status_code=200, content=build_liveness_payload())


@router.get("/health/ready")
def readiness_check() -> JSONResponse:
    """Readiness: safe to receive traffic (database + configuration).

    Returns ``503`` when not ready so load balancers and deploy gates can stop
    routing. AI queue backlog is reported in the body but does not fail readiness.
    """
    payload, ready = build_readiness_payload()
    return JSONResponse(status_code=200 if ready else 503, content=payload)


@router.get("/health")
def health_check() -> JSONResponse:
    """Composite health for humans and demos (always HTTP 200 when process is up).

    Inspect ``status``, ``database``, ``config``, and ``ai``. Deployment probes
    should use ``/health/live`` (liveness) and ``/health/ready`` (readiness).
    """
    payload = build_health_payload()
    return JSONResponse(status_code=200, content=payload)
