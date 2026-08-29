"""Trusted Host header resolution (issue #316).

Local/test default to ``*`` so TestClient (``Host: testserver``) and local
health checks keep working. Staging/production require an explicit
``ALLOWED_HOSTS`` allowlist and fail closed at config validation.

Health-check paths are exempt at enforcement time so an ALB/target-group probe
that sends the instance IP as ``Host`` cannot take the service out of rotation.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.errors import build_error_response, get_request_id

DEPLOYED_ENVIRONMENTS = frozenset({"staging", "production"})
HEALTH_PATHS = frozenset({"/health", "/health/live", "/health/ready"})
_LOCALHOST_MARKERS = ("localhost", "127.0.0.1", "0.0.0.0", "[::1]", "::1")


def parse_allowed_hosts(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return []
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


def is_localhost_host(host: str) -> bool:
    lowered = host.strip().lower()
    hostname = lowered.split(":", maxsplit=1)[0]
    return any(marker == hostname or marker in hostname for marker in _LOCALHOST_MARKERS)


def resolve_allowed_hosts(*, app_env: str, allowed_hosts: str | None) -> list[str]:
    """Resolve the Host allowlist.

    - staging / production: explicit list only (may be empty; validation aborts).
    - local / development / test: configured list, or ``['*']``.
    """
    parsed = parse_allowed_hosts(allowed_hosts)
    env = (app_env or "local").strip().lower()
    if env in DEPLOYED_ENVIRONMENTS:
        return parsed
    return parsed or ["*"]


def host_is_allowed(host_header: str, allowed_hosts: list[str]) -> bool:
    if not allowed_hosts or "*" in allowed_hosts:
        return True
    hostname = host_header.strip().lower().split(":", maxsplit=1)[0]
    if not hostname:
        return False
    for allowed in allowed_hosts:
        if allowed == hostname:
            return True
        if allowed.startswith(".") and (hostname.endswith(allowed) or hostname == allowed[1:]):
            return True
    return False


def reject_untrusted_host(
    request: Request,
    *,
    allowed_hosts: list[str],
) -> JSONResponse | None:
    path = request.url.path.rstrip("/") or "/"
    if path in HEALTH_PATHS:
        return None
    if host_is_allowed(request.headers.get("host", ""), allowed_hosts):
        return None
    return build_error_response(
        code="INVALID_HOST",
        message="The request host is not allowed.",
        request_id=get_request_id(request),
        status_code=400,
    )
