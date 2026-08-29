"""Response security headers for the API process (issue #316).

Browser CSP for the Vite/static SPAs is a hosting concern. This module only
covers headers that are safe and useful on JSON API responses.
"""

from __future__ import annotations

from collections.abc import MutableMapping

DEPLOYED_ENVIRONMENTS = frozenset({"staging", "production"})

DEFAULT_API_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=(), payment=()",
    "Cache-Control": "no-store",
}

HSTS_VALUE = "max-age=63072000; includeSubDomains"


def apply_security_headers(
    headers: MutableMapping[str, str],
    *,
    app_env: str,
    https: bool | None = None,
) -> None:
    """Mutate ``headers`` with API security headers. Never overwrites existing values.

    Staging/production always emit HSTS because TLS terminates at the edge.
    The ``https`` flag is kept for tests that want to assert local HTTP behavior.
    """
    for name, value in DEFAULT_API_HEADERS.items():
        headers.setdefault(name, value)
    env = (app_env or "local").strip().lower()
    deployed = env in DEPLOYED_ENVIRONMENTS
    if deployed if https is None else https and deployed:
        headers.setdefault("Strict-Transport-Security", HSTS_VALUE)
