"""CORS origin resolution for browser frontends (issue #263)."""

from __future__ import annotations

LOCAL_CORS_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:8082",
    "http://127.0.0.1:8082",
    "http://localhost:19006",
    "http://127.0.0.1:19006",
]

_LOCALHOST_MARKERS = ("localhost", "127.0.0.1", "0.0.0.0", "[::1]", "::1")


def parse_cors_allowed_origins(raw: str | None) -> list[str]:
    """Parse a comma-separated CORS allowlist; empty tokens are dropped."""
    if not raw or not raw.strip():
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def is_localhost_origin(origin: str) -> bool:
    lowered = origin.strip().lower()
    return any(marker in lowered for marker in _LOCALHOST_MARKERS)


def resolve_cors_origins(
    *,
    app_env: str,
    cors_allowed_origins: str | None,
) -> list[str]:
    """
    Resolve browser CORS origins by environment.

    - local / development / test: ``CORS_ALLOWED_ORIGINS`` when set, else local defaults
      (admin :5173, citizen-web :5174, Expo ports).
    - staging / production: require an explicit non-localhost allowlist via
      ``CORS_ALLOWED_ORIGINS`` — never silently fall back to localhost defaults.
    """
    parsed = parse_cors_allowed_origins(cors_allowed_origins)
    env = (app_env or "local").strip().lower()
    if env in {"staging", "production"}:
        return parsed
    return parsed or list(LOCAL_CORS_ORIGINS)
