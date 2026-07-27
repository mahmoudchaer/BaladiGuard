from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.health import build_health_payload

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> JSONResponse:
    """Liveness/readiness probe with optional database connectivity check."""
    payload = build_health_payload()
    # Keep returning 200 when the app process is up so local demos and basic
    # liveness probes stay usable. Callers can inspect `status` / `database`.
    return JSONResponse(status_code=200, content=payload)
