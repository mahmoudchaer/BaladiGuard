from __future__ import annotations

from app.config import Settings, get_settings
from app.services.notifications.deep_links import (
    build_notification_ticket_path,
    build_ticket_notification_deep_link,
    resolve_citizen_app_base_url,
)
from app.services.notifications.templates import (
    render_ticket_created,
    render_ticket_resolved,
    render_ticket_updated,
)


def _settings_from_env() -> Settings:
    get_settings.cache_clear()
    return Settings()


def test_build_path_rejects_invalid_tracking_codes():
    assert build_notification_ticket_path("!!") is None
    assert build_notification_ticket_path("short") is None
    assert build_notification_ticket_path("tkt_internal") is None
    assert build_notification_ticket_path("AB23CD") == "/t/AB23CD"


def test_deep_link_uses_base_url_and_tracking_code_only(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CITIZEN_APP_BASE_URL", "https://app.baladiguard.example/")
    settings = _settings_from_env()
    link = build_ticket_notification_deep_link("ab23cd", settings=settings)
    assert link == "https://app.baladiguard.example/t/AB23CD"
    assert "tkt_" not in link
    assert "token" not in link.lower()
    assert "@" not in link


def test_deep_link_defaults_localhost_outside_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.delenv("CITIZEN_APP_BASE_URL", raising=False)
    settings = _settings_from_env()
    assert resolve_citizen_app_base_url(settings) == "http://localhost:8081"
    link = build_ticket_notification_deep_link("AB23CD", settings=settings)
    assert link == "http://localhost:8081/t/AB23CD"


def test_deep_link_no_silent_localhost_default_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CITIZEN_APP_BASE_URL", raising=False)
    settings = _settings_from_env()
    assert resolve_citizen_app_base_url(settings) is None
    assert build_ticket_notification_deep_link("AB23CD", settings=settings) is None


def test_templates_include_deep_link_without_raw_ticket_id_in_body(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CITIZEN_APP_BASE_URL", "https://citizen.example")
    get_settings.cache_clear()

    created = render_ticket_created(
        ticket_id="tkt_abc123",
        ticket_number="BG-2026-0042",
        tracking_code="AB23CD",
    )
    updated = render_ticket_updated(
        ticket_id="tkt_abc123",
        status="IN_PROGRESS",
        ticket_number="BG-2026-0042",
        tracking_code="AB23CD",
    )
    resolved = render_ticket_resolved(
        ticket_id="tkt_abc123",
        ticket_number="BG-2026-0042",
        tracking_code="AB23CD",
    )

    for message in (created, updated, resolved):
        assert message.ticket_id == "tkt_abc123"
        assert "tkt_abc123" not in message.body
        assert "tkt_abc123" not in message.subject
        assert "BG-2026-0042" in message.body
        assert "Tracking code: AB23CD." in message.body
        assert "View details: https://citizen.example/t/AB23CD" in message.body
        assert message.deep_link == "https://citizen.example/t/AB23CD"
        assert message.as_dict().get("deepLink") == message.deep_link
        lower = message.body.lower()
        assert "+961" not in lower
        assert "password" not in lower
        assert "object key" not in lower

    get_settings.cache_clear()


def test_templates_omit_link_when_tracking_code_missing(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CITIZEN_APP_BASE_URL", "https://citizen.example")
    get_settings.cache_clear()

    message = render_ticket_updated(ticket_id="tkt_1", status="ASSIGNED")
    assert message.deep_link is None
    assert "View details:" not in message.body
    assert "your report" in message.body
    get_settings.cache_clear()
