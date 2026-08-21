"""WhatsApp channel unit/integration coverage (issue #296) — mock provider, no Meta number."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database.memory import ticket_store
from app.database.memory_content_safety_job import content_safety_job_store
from app.database.memory_whatsapp import whatsapp_conversation_store, whatsapp_dedup_store
from app.main import create_app
from app.services.whatsapp.fsm import WhatsAppFlowEngine
from app.services.whatsapp.graph import get_mock_graph_client, reset_mock_graph_client
from app.services.whatsapp.signature import sign_meta_payload
from app.services.whatsapp.states import parse_command, previous_editable_state
from app.services.whatsapp.webhook_parse import parse_webhook_payload

APP_SECRET = "test-whatsapp-app-secret"
VERIFY_TOKEN = "test-whatsapp-verify-token"
PHONE_NUMBER_ID = "pnid_test_001"


@pytest.fixture
def whatsapp_env(monkeypatch):
    monkeypatch.setenv("WHATSAPP_ENABLED", "true")
    monkeypatch.setenv("WHATSAPP_PROVIDER", "mock")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", APP_SECRET)
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", VERIFY_TOKEN)
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", PHONE_NUMBER_ID)
    get_settings.cache_clear()
    whatsapp_conversation_store.clear()
    whatsapp_dedup_store.clear()
    content_safety_job_store.clear()
    reset_mock_graph_client()
    yield
    get_settings.cache_clear()
    whatsapp_conversation_store.clear()
    whatsapp_dedup_store.clear()
    content_safety_job_store.clear()
    reset_mock_graph_client()


@pytest.fixture
def wa_client(whatsapp_env):
    return TestClient(create_app())


def _message_payload(*, message_id: str, wa_id: str, message: dict) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_test",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": PHONE_NUMBER_ID},
                            "contacts": [{"wa_id": wa_id}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": message_id,
                                    "timestamp": "1710000000",
                                    **message,
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _post_event(client: TestClient, payload: dict) -> dict:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    response = client.post(
        "/v1/whatsapp/webhook",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sign_meta_payload(app_secret=APP_SECRET, raw_body=raw),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_parse_command_and_back_transition():
    assert parse_command("HELP") == "help"
    assert parse_command("إلغاء") == "cancel"
    assert previous_editable_state("description") == "language"
    assert previous_editable_state("welcome") is None


def test_parse_webhook_ignores_status_receipts():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": PHONE_NUMBER_ID},
                            "statuses": [{"id": "wamid.status", "status": "delivered"}],
                            "messages": [],
                        }
                    }
                ]
            }
        ],
    }
    events = parse_webhook_payload(payload)
    assert len(events) == 1
    assert events[0].kind == "status"


def test_webhook_verify_challenge(wa_client):
    response = wa_client.get(
        "/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "challenge-123",
        },
    )
    assert response.status_code == 200
    assert response.text == "challenge-123"


def test_webhook_rejects_bad_signature(wa_client):
    payload = _message_payload(
        message_id="wamid.bad",
        wa_id="96170111111",
        message={"type": "text", "text": {"body": "hi"}},
    )
    raw = json.dumps(payload).encode("utf-8")
    response = wa_client.post(
        "/v1/whatsapp/webhook",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    assert response.status_code == 403


def test_duplicate_message_is_deduped(wa_client):
    payload = _message_payload(
        message_id="wamid.dup.1",
        wa_id="96170111112",
        message={"type": "text", "text": {"body": "hello"}},
    )
    first = _post_event(wa_client, payload)
    second = _post_event(wa_client, payload)
    assert first["accepted"] == 1
    assert second["duplicates"] == 1
    assert second["accepted"] == 0


def test_failed_processing_releases_dedup_so_retry_is_processed(wa_client, monkeypatch):
    payload = _message_payload(
        message_id="wamid.retry.1",
        wa_id="96170111113",
        message={"type": "text", "text": {"body": "hello"}},
    )
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sign_meta_payload(app_secret=APP_SECRET, raw_body=raw),
    }
    original = WhatsAppFlowEngine.handle_event
    should_fail = {"value": True}

    def maybe_fail(self, event):
        if should_fail["value"]:
            raise RuntimeError("transient graph/s3 failure")
        return original(self, event)

    monkeypatch.setattr(WhatsAppFlowEngine, "handle_event", maybe_fail)
    failed = wa_client.post("/v1/whatsapp/webhook", content=raw, headers=headers)
    assert failed.status_code == 503, failed.text
    assert failed.json()["failed"] == 1
    assert failed.json()["accepted"] == 0

    should_fail["value"] = False
    retried = wa_client.post("/v1/whatsapp/webhook", content=raw, headers=headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["accepted"] == 1
    assert retried.json()["duplicates"] == 0


def test_outbound_graph_failure_keeps_webhook_retryable(wa_client, monkeypatch):
    payload = _message_payload(
        message_id="wamid.outbound.fail",
        wa_id="96170111114",
        message={"type": "text", "text": {"body": "hello"}},
    )
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sign_meta_payload(app_secret=APP_SECRET, raw_body=raw),
    }
    mock = get_mock_graph_client()
    original = mock.send_text
    should_fail = {"value": True}

    def maybe_fail(*, phone_number_id: str, to_wa_id: str, body: str):
        if should_fail["value"]:
            raise RuntimeError("graph down")
        return original(phone_number_id=phone_number_id, to_wa_id=to_wa_id, body=body)

    monkeypatch.setattr(mock, "send_text", maybe_fail)
    failed = wa_client.post("/v1/whatsapp/webhook", content=raw, headers=headers)
    assert failed.status_code == 503, failed.text
    assert failed.json()["failed"] == 1
    assert failed.json()["accepted"] == 0
    assert mock.sent == []

    should_fail["value"] = False
    retried = wa_client.post("/v1/whatsapp/webhook", content=raw, headers=headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["accepted"] == 1
    assert retried.json()["duplicates"] == 0
    assert mock.sent


def test_flow_advances_and_submits_ticket(wa_client, monkeypatch):
    wa_id = "96170999888"
    mock = get_mock_graph_client()

    def fake_upload(contents: bytes, *, owner_user_id: str, content_type=None, filename=None):
        return f"reports/temp/wa/{owner_user_id}/photo.jpg"

    monkeypatch.setattr(
        "app.services.whatsapp.fsm.photo_upload_service.upload_report_photo_bytes",
        fake_upload,
    )

    steps = [
        ("wamid.1", {"type": "text", "text": {"body": "hi"}}),
        ("wamid.2", {"type": "text", "text": {"body": "YES"}}),
        ("wamid.3", {"type": "text", "text": {"body": "EN"}}),
        (
            "wamid.4",
            {
                "type": "text",
                "text": {"body": "Large pothole near the university gate blocking cars."},
            },
        ),
        (
            "wamid.5",
            {
                "type": "location",
                "location": {
                    "latitude": 33.896112,
                    "longitude": 35.478419,
                    "name": "Hamra",
                    "address": "Near AUB Main Gate, Hamra, Beirut",
                },
            },
        ),
        (
            "wamid.6",
            {"type": "image", "image": {"id": "media_1", "mime_type": "image/jpeg"}},
        ),
        ("wamid.7", {"type": "text", "text": {"body": "SKIP"}}),
        ("wamid.8", {"type": "text", "text": {"body": "CONFIRM"}}),
    ]
    for message_id, message in steps:
        result = _post_event(
            wa_client,
            _message_payload(message_id=message_id, wa_id=wa_id, message=message),
        )
        assert result["accepted"] == 1

    assert mock.sent, "expected outbound prompts"
    assert any("Report submitted" in msg.body or "Ticket:" in msg.body for msg in mock.sent)

    # Ticket persisted for the reconciled WhatsApp phone owner.
    tickets = list(ticket_store._tickets.values())  # noqa: SLF001 - test inspection
    submitted = [ticket for ticket in tickets if "pothole" in ticket.description.lower()]
    assert submitted
    safety_ticket_ids = {job.ticket_id for job in content_safety_job_store.list()}
    assert submitted[0].ticket_id in safety_ticket_ids


def test_submitting_ack_failure_resumes_submit_on_retry(wa_client, monkeypatch):
    wa_id = "96170111115"
    mock = get_mock_graph_client()

    def fake_upload(contents: bytes, *, owner_user_id: str, content_type=None, filename=None):
        return f"reports/temp/wa/{owner_user_id}/photo.jpg"

    monkeypatch.setattr(
        "app.services.whatsapp.fsm.photo_upload_service.upload_report_photo_bytes",
        fake_upload,
    )
    setup_steps = [
        ("wamid.sub.1", {"type": "text", "text": {"body": "hi"}}),
        ("wamid.sub.2", {"type": "text", "text": {"body": "YES"}}),
        ("wamid.sub.3", {"type": "text", "text": {"body": "EN"}}),
        (
            "wamid.sub.4",
            {
                "type": "text",
                "text": {"body": "Broken streetlight on the corner after midnight."},
            },
        ),
        (
            "wamid.sub.5",
            {
                "type": "location",
                "location": {
                    "latitude": 33.896112,
                    "longitude": 35.478419,
                    "name": "Hamra",
                    "address": "Near AUB Main Gate, Hamra, Beirut",
                },
            },
        ),
        (
            "wamid.sub.6",
            {"type": "image", "image": {"id": "media_1", "mime_type": "image/jpeg"}},
        ),
        ("wamid.sub.7", {"type": "text", "text": {"body": "SKIP"}}),
    ]
    for message_id, message in setup_steps:
        result = _post_event(
            wa_client,
            _message_payload(message_id=message_id, wa_id=wa_id, message=message),
        )
        assert result["accepted"] == 1

    original = mock.send_text

    def fail_submitting_ack(*, phone_number_id: str, to_wa_id: str, body: str):
        if "Submitting" in body or "جارٍ إرسال" in body:
            raise RuntimeError("graph down on submitting ack")
        return original(phone_number_id=phone_number_id, to_wa_id=to_wa_id, body=body)

    monkeypatch.setattr(mock, "send_text", fail_submitting_ack)
    confirm_payload = _message_payload(
        message_id="wamid.sub.8",
        wa_id=wa_id,
        message={"type": "text", "text": {"body": "CONFIRM"}},
    )
    raw = json.dumps(confirm_payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sign_meta_payload(app_secret=APP_SECRET, raw_body=raw),
    }
    failed = wa_client.post("/v1/whatsapp/webhook", content=raw, headers=headers)
    assert failed.status_code == 503, failed.text
    assert failed.json()["failed"] == 1
    tickets_before = [
        ticket
        for ticket in ticket_store._tickets.values()  # noqa: SLF001
        if "streetlight" in ticket.description.lower()
    ]
    assert tickets_before == []

    monkeypatch.setattr(mock, "send_text", original)
    retried = wa_client.post("/v1/whatsapp/webhook", content=raw, headers=headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["accepted"] == 1
    assert retried.json()["duplicates"] == 0
    tickets_after = [
        ticket
        for ticket in ticket_store._tickets.values()  # noqa: SLF001
        if "streetlight" in ticket.description.lower()
    ]
    assert tickets_after
    assert any("Report submitted" in msg.body or "Ticket:" in msg.body for msg in mock.sent)


def test_disabled_channel_returns_503(monkeypatch):
    monkeypatch.setenv("WHATSAPP_ENABLED", "false")
    get_settings.cache_clear()
    client = TestClient(create_app())
    response = client.get(
        "/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "x",
            "hub.challenge": "y",
        },
    )
    assert response.status_code == 503
    get_settings.cache_clear()
