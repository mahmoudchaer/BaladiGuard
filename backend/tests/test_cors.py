"""CORS origin resolution coverage for issue #263."""

from app.core.cors import LOCAL_CORS_ORIGINS, resolve_cors_origins


def test_local_defaults_include_citizen_web_port():
    origins = resolve_cors_origins(app_env="local", cors_allowed_origins=None)
    assert origins == LOCAL_CORS_ORIGINS
    assert "http://localhost:5174" in origins


def test_local_can_override_allowlist():
    origins = resolve_cors_origins(
        app_env="development",
        cors_allowed_origins="http://localhost:4000, http://127.0.0.1:4000",
    )
    assert origins == ["http://localhost:4000", "http://127.0.0.1:4000"]


def test_staging_requires_explicit_allowlist_without_localhost_fallback():
    assert resolve_cors_origins(app_env="staging", cors_allowed_origins=None) == []
    origins = resolve_cors_origins(
        app_env="production",
        cors_allowed_origins="https://citizen.example.com,https://admin.example.com",
    )
    assert origins == ["https://citizen.example.com", "https://admin.example.com"]
