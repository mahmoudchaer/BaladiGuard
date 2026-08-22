"""Compose request-time hardening checks for the HTTP middleware (issue #316).

Path-based rate limits cover export, ops, and staff mutations without editing
citizen/ops route modules that overlap with the privacy/legal PR.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.body_limits import (
    attach_body_byte_limit,
    max_body_bytes_for_request,
    reject_oversized_body,
    reject_oversized_headers,
)
from app.core.rate_limit import enforce_rate_limit
from app.core.trusted_hosts import reject_untrusted_host, resolve_allowed_hosts

_STAFF_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_STAFF_WRITE_PREFIXES = (
    "/v1/tickets/",
    "/v1/work-orders",
    "/v1/workforce",
    "/v1/admin/",
    "/v1/resolution-reviews",
    "/v1/resolution-feedback",
)


def _path(request: Request) -> str:
    return request.url.path.rstrip("/") or "/"


def match_path_rate_limit_policy(request: Request) -> str | None:
    path = _path(request)
    method = request.method.upper()

    if path == "/v1/citizen/me/export" and method == "GET":
        return "citizen-data-export"
    if path == "/v1/citizen/me/delete" and method == "POST":
        return "citizen-data-delete"
    if path.startswith("/v1/ops"):
        return "ops-dashboard"
    if method in _STAFF_WRITE_METHODS:
        if path == "/v1/tickets":
            return None
        if any(path.startswith(prefix) for prefix in _STAFF_WRITE_PREFIXES):
            return "staff-mutation"
    return None


def _extra_identity(request: Request) -> str | None:
    authorization = request.headers.get("authorization")
    if authorization:
        return authorization.strip()
    cookie = request.headers.get("cookie")
    if cookie:
        return cookie.strip()[:256]
    return None


def enforce_path_rate_limit(request: Request) -> JSONResponse | None:
    policy = match_path_rate_limit_policy(request)
    if policy is None:
        return None
    return enforce_rate_limit(
        request,
        policy,
        extra_identity=_extra_identity(request),
        message="Too many requests. Please wait before trying again.",
    )


def reject_hardened_request(request: Request) -> JSONResponse | None:
    """Run cheap pre-handler checks. Returns a response to short-circuit, else None."""
    settings = get_settings()
    rejected = reject_oversized_headers(request, max_header_bytes=settings.max_header_bytes)
    if rejected is not None:
        return rejected

    allowed_hosts = resolve_allowed_hosts(
        app_env=settings.app_env,
        allowed_hosts=settings.allowed_hosts,
    )
    rejected = reject_untrusted_host(request, allowed_hosts=allowed_hosts)
    if rejected is not None:
        return rejected

    max_bytes = max_body_bytes_for_request(
        request,
        json_max_bytes=settings.max_json_body_bytes,
        webhook_max_bytes=settings.whatsapp_max_webhook_bytes,
    )
    rejected = reject_oversized_body(request, max_bytes=max_bytes)
    if rejected is not None:
        return rejected

    attach_body_byte_limit(request, max_bytes=max_bytes)
    return enforce_path_rate_limit(request)
