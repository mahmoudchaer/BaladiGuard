"""Configuration validation coverage for issue #147."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.core.config_validation import validate_configuration
from app.main import create_app
from app.services.health import build_health_payload


def _settings_from_env() -> Settings:
    get_settings.cache_clear()
    return Settings()


def test_local_defaults_are_valid():
    environ = {
        "APP_ENV": "local",
        "DATABASE_BACKEND": "memory",
        "NOTIFICATION_ADAPTER": "mock",
        "AWS_REGION": "us-east-1",
    }
    result = validate_configuration(_settings_from_env(), environ=environ)
    assert result.env == "local"
    assert result.ok
    assert result.should_abort_startup is False
    assert result.to_health_dict() == {"status": "ok", "issues": []}


def test_invalid_database_backend_is_reported():
    environ = {
        "APP_ENV": "local",
        "DATABASE_BACKEND": "postgres",
        "AWS_REGION": "us-east-1",
    }
    result = validate_configuration(_settings_from_env(), environ=environ)
    assert result.ok is False
    assert any(issue.code == "INVALID_DATABASE_BACKEND" for issue in result.issues)


def test_invalid_app_env_is_reported_and_aborts_startup():
    environ = {"APP_ENV": "staging", "AWS_REGION": "us-east-1"}
    result = validate_configuration(_settings_from_env(), environ=environ)
    assert any(issue.code == "INVALID_APP_ENV" for issue in result.issues)
    assert result.should_abort_startup is True


def test_prod_alias_normalizes_to_production_and_applies_rules():
    environ = {
        "APP_ENV": "prod",
        "DATABASE_BACKEND": "memory",
        "NOTIFICATION_ADAPTER": "mock",
        "SECRET_KEY": "",
        "AWS_REGION": "us-east-1",
    }
    result = validate_configuration(_settings_from_env(), environ=environ)
    assert result.env == "production"
    assert result.should_abort_startup is True
    assert any(issue.code == "UNSAFE_DATABASE_BACKEND" for issue in result.issues)
    assert not any(issue.code == "INVALID_APP_ENV" for issue in result.issues)


def test_invalid_numeric_settings_are_reported():
    environ = {
        "APP_ENV": "local",
        "AWS_REGION": "us-east-1",
        "DUPLICATE_MIN_SCORE": "not-a-number",
        "AI_PROCESSING_CLAIM_TIMEOUT_SECONDS": "0",
    }
    result = validate_configuration(_settings_from_env(), environ=environ)
    codes = {issue.code for issue in result.issues}
    assert "INVALID_DUPLICATE_MIN_SCORE" in codes
    assert "INVALID_AI_PROCESSING_CLAIM_TIMEOUT_SECONDS" in codes


def test_production_rejects_development_defaults():
    environ = {
        "APP_ENV": "production",
        "DATABASE_BACKEND": "memory",
        "NOTIFICATION_ADAPTER": "mock",
        "SECRET_KEY": "changeme",
        "AWS_REGION": "us-east-1",
        "AWS_S3_BUCKET": "",
        "LOCATION_PLACE_INDEX_NAME": "",
        "SEED_SAMPLE_TICKETS": "true",
        "DYNAMODB_ENDPOINT_URL": "http://localhost:8001",
    }
    # Build settings reflecting those env vars.
    original = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(environ)
        settings = _settings_from_env()
        result = validate_configuration(settings, environ=environ)
    finally:
        os.environ.clear()
        os.environ.update(original)
        get_settings.cache_clear()

    codes = {issue.code for issue in result.issues}
    assert result.should_abort_startup is True
    assert "UNSAFE_DATABASE_BACKEND" in codes
    assert "UNSAFE_NOTIFICATION_ADAPTER" in codes
    assert "UNSAFE_SECRET_KEY" in codes
    assert "UNSAFE_STAFF_PASSWORD" in codes
    assert "MISSING_LOCATION_PLACE_INDEX_NAME" in codes
    assert "MISSING_AWS_S3_BUCKET" in codes
    assert "UNSAFE_DYNAMODB_ENDPOINT_URL" in codes
    assert "UNSAFE_SEED_SAMPLE_TICKETS" in codes
    # Secret values must never appear in issue messages.
    serialized = " ".join(issue.message for issue in result.issues).lower()
    assert "changeme" not in serialized
    assert "staff-demo-password" not in serialized


def test_production_valid_configuration_passes():
    environ = {
        "APP_ENV": "production",
        "DATABASE_BACKEND": "dynamodb",
        "NOTIFICATION_ADAPTER": "real",
        "SECRET_KEY": "prod-rotation-key-not-a-placeholder",
        "STAFF_USERNAME": "ops",
        "STAFF_PASSWORD": "rotated-staff-password-not-demo",
        "AWS_REGION": "us-east-1",
        "AWS_S3_BUCKET": "baladiguard-prod-uploads",
        "LOCATION_PLACE_INDEX_NAME": "baladiguard-places",
        "SEED_SAMPLE_TICKETS": "false",
        "DYNAMODB_ENDPOINT_URL": "",
    }
    original = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(environ)
        settings = _settings_from_env()
        result = validate_configuration(settings, environ=environ)
    finally:
        os.environ.clear()
        os.environ.update(original)
        get_settings.cache_clear()

    assert result.ok
    assert result.should_abort_startup is False


def test_health_payload_includes_config_without_secrets(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "config" in body
    assert body["config"]["status"] in {"ok", "error"}
    assert isinstance(body["config"]["issues"], list)
    serialized = str(body).lower()
    assert "staff-demo-password" not in serialized
    assert "secret_key" not in serialized or "unsafe_secret_key" in serialized


def test_build_health_payload_marks_degraded_on_config_errors(monkeypatch):
    def bad_config():
        return {
            "status": "error",
            "issues": [
                {
                    "code": "INVALID_DATABASE_BACKEND",
                    "message": "DATABASE_BACKEND must be 'memory' or 'dynamodb'.",
                    "severity": "error",
                }
            ],
        }

    monkeypatch.setattr("app.services.health.check_configuration", bad_config)
    payload = build_health_payload()
    assert payload["status"] == "degraded"
    assert payload["config"]["status"] == "error"


def test_production_startup_aborts_on_unsafe_config(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_BACKEND", "memory")
    monkeypatch.setenv("NOTIFICATION_ADAPTER", "mock")
    monkeypatch.setenv("SECRET_KEY", "")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.delenv("AWS_S3_BUCKET", raising=False)
    monkeypatch.delenv("LOCATION_PLACE_INDEX_NAME", raising=False)
    get_settings.cache_clear()

    app = create_app()
    with pytest.raises(RuntimeError, match="Configuration validation failed"):
        with TestClient(app):
            pass

    # Restore test defaults for later fixtures in this process.
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_BACKEND", "memory")
    get_settings.cache_clear()


def test_invalid_app_env_startup_aborts(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("DATABASE_BACKEND", "memory")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    get_settings.cache_clear()

    app = create_app()
    with pytest.raises(RuntimeError, match="Configuration validation failed"):
        with TestClient(app):
            pass

    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()
